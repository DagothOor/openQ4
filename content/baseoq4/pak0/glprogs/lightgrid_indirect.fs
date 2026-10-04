#version 110
// openQ4 Light: baked indirect (bounced) light for every opaque surface.
//
// Controlled by cvars (uLightGridParams):
//   r_lightGridAO 1          - physically based mode: GTAO with multi-bounce
//                              darkens only this indirect light (lamps keep
//                              their exact stencil shadows); the full-frame
//                              r_ssao pass is skipped where a grid exists.
//                              0 = no AO here (stock behaviour).
//   r_lightGridShadowFloor   - minimum indirect irradiance. The bake stores
//                              8-bit probes, so faint multi-bounce light under
//                              1/255 is lost and corners went pure black. Only
//                              a texture that is itself black stays black.
//   r_lightGridIntensity     - scales the whole contribution (stock cvar)
//   r_lightGridIrradianceGamma - decode of the baked LDR probes (stock cvar)
// Also: when all 8 probes around a point are invalid (inside geometry), probes
// one and two grid cells out along the surface normal are used instead of
// leaving the surface black.
//
//   kAORadius     - AO radius in world units. 128: detail scales measured on
//                   Q4 buffers end there, and the grid (64x64x128 spacing)
//                   only resolves variation above ~128, so no double counting
//   kAOThickness  - assumed occluder thickness as a fraction of the radius
//   kAOSlices     - directions per pixel (quality), 6 steps per side each
//   kMultiBounce  - 1 = use albedo multi-bounce, 0 = plain AO
const float kAORadius = 128.0;
const float kAOThickness = 0.5;
const int kAOSlices = 4;
#define kMultiBounce 1


uniform sampler2D uBumpMap;
uniform sampler2D uDiffuseMap;
uniform sampler2D uLightGridAtlas;
uniform sampler2D uLightGridVisibilityAtlas;
uniform sampler2D uLightGridProbeAtlas;
uniform sampler2D uSceneDepth;

uniform vec4 uLightGridOrigin;
uniform vec4 uLightGridSize;
uniform vec4 uLightGridBounds;
uniform vec4 uAtlasInfo;
uniform vec4 uVisibilityInfo;
uniform vec4 uProbeInfo;
uniform vec4 uBlendInfo;
uniform vec4 uPortalPlane;
uniform vec4 uPortalBoundsMin;
uniform vec4 uPortalBoundsMax;
uniform vec4 uDebugInfo;
uniform vec4 uDepthInfo;
uniform vec4 uDepthViewport;
uniform vec4 uColorInfo;
uniform vec4 uDiffuseColor;
uniform vec4 uFlatDiffuseParams;
uniform vec4 uLightGridParams;

varying vec2 vBumpTexCoord;
varying vec2 vDiffuseTexCoord;
varying vec3 vWorldTangent;
varying vec3 vWorldBitangent;
varying vec3 vWorldNormal;
varying vec3 vWorldPosition;
varying vec3 vVertexColor;
varying float vLocalZ;

vec2 SignNotZero( vec2 value ) {
	return vec2( value.x >= 0.0 ? 1.0 : -1.0, value.y >= 0.0 ? 1.0 : -1.0 );
}

vec3 SafeNormalize( vec3 value ) {
	return value * inversesqrt( max( dot( value, value ), 1.0e-8 ) );
}

vec3 DecodeBakedIrradiance( vec3 value ) {
	float gamma = max( uColorInfo.x, 0.001 );
	return pow( max( value, vec3( 0.0 ) ), vec3( gamma ) );
}

// Albedo cap for the baked light only. Quake 4 textures were balanced by hand
// against their lamps: light-coloured models (ships, debris) often sit in weak
// direct light. Baked light falls on everything evenly and would reveal their
// full texture brightness, so they glow. Texture brightness used for THIS light
// stays linear up to kAlbedoKnee and rolls off smoothly towards kAlbedoCap;
// colour is kept. Direct light is not affected. kAlbedoCap 0 = off.
const float kAlbedoKnee = 0.25;
const float kAlbedoCap = 0.0;  // 0 = off (physical); 0.4 = tame light-coloured models

vec3 CapAlbedo( vec3 a ) {
	if ( kAlbedoCap <= 0.0 ) {
		return a;
	}
	float y = dot( a, vec3( 0.2126, 0.7152, 0.0722 ) );
	if ( y <= kAlbedoKnee ) {
		return a;
	}
	float range = kAlbedoCap - kAlbedoKnee;
	float yc = kAlbedoKnee + range * ( 1.0 - exp( -( y - kAlbedoKnee ) / range ) );
	return a * ( yc / y );
}

vec3 ShapeLightGridContribution( vec3 value ) {
	float maxContribution = uColorInfo.y;
	if ( maxContribution > 0.0 ) {
		value = min( value, vec3( maxContribution ) );
	}
	return max( value, vec3( 0.0 ) );
}

vec3 ApplyFlatDiffuseSweep( vec3 diffuse, float localZ ) {
	if ( uFlatDiffuseParams.x <= 0.0 ) {
		return diffuse;
	}
	float height = clamp( ( localZ - uFlatDiffuseParams.y ) * uFlatDiffuseParams.z, 0.0, 1.0 );
	float distanceToBand = abs( height - fract( uFlatDiffuseParams.w ) );
	distanceToBand = min( distanceToBand, 1.0 - distanceToBand );
	float band = 1.0 - smoothstep( 0.045, 0.16, distanceToBand );
	return mix( diffuse, vec3( 1.0 ), uFlatDiffuseParams.x * band );
}

vec3 DecodeLocalNormal( vec4 bumpSample ) {
	vec2 localNormalXY = vec2( bumpSample.a, bumpSample.g ) * 2.0 - 1.0;
	float xyLengthSq = dot( localNormalXY, localNormalXY );
	if ( xyLengthSq > 1.0 ) {
		localNormalXY *= inversesqrt( xyLengthSq );
		xyLengthSq = 1.0;
	}

	float encodedZ = max( bumpSample.b * 2.0 - 1.0, 0.0 );
	float reconstructedZ = sqrt( max( 1.0 - xyLengthSq, 0.0 ) );
	return SafeNormalize( vec3( localNormalXY, mix( encodedZ, reconstructedZ, 0.75 ) ) );
}

vec2 OctEncode( vec3 normal ) {
	float invLength = 1.0 / max( abs( normal.x ) + abs( normal.y ) + abs( normal.z ), 1.0e-4 );
	vec3 n = normal * invLength;
	vec2 oct = n.xy;
	if ( n.z < 0.0 ) {
		oct = ( vec2( 1.0 ) - abs( oct.yx ) ) * SignNotZero( oct );
	}
	return oct;
}

void ComputeGridAxis( float lightOrigin, float cellSize, float bound, out float gridCoord, out float fracCoord ) {
	if ( bound <= 1.0 || cellSize <= 0.0 ) {
		gridCoord = 0.0;
		fracCoord = 0.0;
		return;
	}

	float position = max( 0.0, lightOrigin / cellSize );
	gridCoord = floor( position );
	fracCoord = position - gridCoord;

	if ( gridCoord < 0.0 ) {
		gridCoord = 0.0;
		fracCoord = 0.0;
	} else if ( gridCoord >= bound - 1.0 ) {
		gridCoord = bound - 1.0;
		fracCoord = 0.0;
	}
}

vec2 ProbeAtlasCoord( vec3 sampleCoord, vec2 octCoord ) {
	float tileSize = max( uAtlasInfo.z, 1.0 );
	float borderSize = max( uAtlasInfo.w, 0.0 );
	float activeSize = max( tileSize - borderSize, 1.0 );
	float cellIndex = sampleCoord.x + sampleCoord.z * uLightGridBounds.x;
	vec2 probeOriginPixels = vec2( cellIndex * tileSize, sampleCoord.y * tileSize );
	vec2 samplePixels = probeOriginPixels + vec2( borderSize * 0.5 ) + octCoord * activeSize;
	return samplePixels * uAtlasInfo.xy;
}

vec2 ProbeGridCoord( vec3 sampleCoord ) {
	float invCellsX = 1.0 / max( uLightGridBounds.x * uLightGridBounds.z, 1.0 );
	float invCellsY = 1.0 / max( uLightGridBounds.y, 1.0 );
	float cellIndex = sampleCoord.x + sampleCoord.z * uLightGridBounds.x;
	return vec2( ( cellIndex + 0.5 ) * invCellsX, ( sampleCoord.y + 0.5 ) * invCellsY );
}

vec3 ProbeWorldPosition( vec3 sampleCoord ) {
	vec3 idealPosition = uLightGridOrigin.xyz + sampleCoord * uLightGridSize.xyz;
	if ( uProbeInfo.y <= 0.0 ) {
		return idealPosition;
	}

	vec3 encodedRelocation = texture2D( uLightGridProbeAtlas, ProbeGridCoord( sampleCoord ) ).rgb * 255.0;
	vec3 relocation = ( encodedRelocation - vec3( 128.0 ) ) * ( uProbeInfo.x / 127.0 );
	return idealPosition + relocation;
}

float VisibilityWeight( vec4 moments, float receiverDistance, vec3 worldNormal, vec3 probeToReceiverDir ) {
	if ( moments.b <= 0.001 ) {
		return 1.0;
	}

	float maxDistance = max( uVisibilityInfo.x, 1.0 );
	float meanDistance = moments.r * maxDistance;
	float meanDistanceSq = moments.g * maxDistance * maxDistance;
	float normalBias = uVisibilityInfo.y * ( 0.25 + 0.75 * max( dot( worldNormal, -probeToReceiverDir ), 0.0 ) );
	float biasedDistance = max( receiverDistance - normalBias, 0.0 );
	if ( biasedDistance <= meanDistance ) {
		return 1.0;
	}

	float variance = max( meanDistanceSq - meanDistance * meanDistance, maxDistance * maxDistance * 0.000025 );
	float delta = biasedDistance - meanDistance;
	float chebyshev = variance / ( variance + delta * delta );
	chebyshev = clamp( chebyshev, 0.0, 1.0 );
	return clamp( pow( chebyshev, max( uVisibilityInfo.w, 1.0 ) ), uVisibilityInfo.z, 1.0 );
}

float LightGridContributionScale() {
	if ( abs( uBlendInfo.y ) <= 0.001 || uBlendInfo.z <= 0.0 ) {
		return uBlendInfo.x;
	}

	float portalDistance = abs( dot( vWorldPosition, uPortalPlane.xyz ) + uPortalPlane.w );
	vec3 nearestPortalBoundsPoint = clamp( vWorldPosition, uPortalBoundsMin.xyz, uPortalBoundsMax.xyz );
	float apertureDistance = length( vWorldPosition - nearestPortalBoundsPoint );
	float portalFade =
		( 1.0 - smoothstep( 0.0, uBlendInfo.z, portalDistance ) ) *
		( 1.0 - smoothstep( 0.0, uBlendInfo.z, apertureDistance ) );
	float neighborWeight = 0.5 * portalFade;
	float blendWeight = uBlendInfo.y > 0.0 ? neighborWeight : 1.0 - neighborWeight;
	return uBlendInfo.x * blendWeight;
}

vec2 LightGridDepthCoord() {
	return ( gl_FragCoord.xy - uDepthViewport.xy ) * uDepthInfo.xy;
}

bool LightGridDepthCoordValid( vec2 depthCoord ) {
	return depthCoord.x >= 0.0 && depthCoord.y >= 0.0 && depthCoord.x <= 1.0 && depthCoord.y <= 1.0;
}

float LightGridSceneDepth( vec2 depthCoord ) {
	return texture2D( uSceneDepth, depthCoord ).r;
}

bool LightGridDepthAccepted() {
	if ( uDepthInfo.w <= 0.5 ) {
		return true;
	}

	vec2 depthCoord = LightGridDepthCoord();
	if ( !LightGridDepthCoordValid( depthCoord ) ) {
		return false;
	}

	float sceneDepth = LightGridSceneDepth( depthCoord );
	return gl_FragCoord.z <= sceneDepth + uDepthInfo.z;
}


// ---------------- GTAO on the captured scene depth ----------------

const int kAOSteps = 6;
const float kAOPi = 3.14159265;
const float kAOHalfPi = 1.57079633;

float AO_P0() { return gl_ProjectionMatrix[0][0]; }
float AO_P5() { return gl_ProjectionMatrix[1][1]; }
float AO_P8() { return gl_ProjectionMatrix[2][0]; }
float AO_P9() { return gl_ProjectionMatrix[2][1]; }

float AO_ViewZ( float depth ) {
	float denom = depth * 2.0 - 1.0 + gl_ProjectionMatrix[2][2];
	if ( abs( denom ) < 0.00001 ) {
		denom = ( denom < 0.0 ) ? -0.00001 : 0.00001;
	}
	return -gl_ProjectionMatrix[3][2] / denom;
}

float AO_Depth( vec2 uv ) {
	return texture2D( uSceneDepth, uv ).r;
}

vec3 AO_ViewPos( vec2 uv, float depth ) {
	float z = AO_ViewZ( depth );
	vec2 ndc = uv * 2.0 - 1.0;
	return vec3( -z * ( ndc.x + AO_P8() ) / AO_P0(), -z * ( ndc.y + AO_P9() ) / AO_P5(), z );
}

vec3 AO_PickDerivative( vec3 c, vec3 n, vec3 p ) {
	vec3 a = c - n;
	vec3 b = p - c;
	return ( abs( a.z ) < abs( b.z ) ) ? a : b;
}

vec3 AO_Normal( vec2 uv, vec3 c, vec2 texel ) {
	vec2 dx = vec2( texel.x, 0.0 );
	vec2 dy = vec2( 0.0, texel.y );
	vec3 l = AO_ViewPos( uv - dx, AO_Depth( uv - dx ) );
	vec3 r = AO_ViewPos( uv + dx, AO_Depth( uv + dx ) );
	vec3 d = AO_ViewPos( uv - dy, AO_Depth( uv - dy ) );
	vec3 u = AO_ViewPos( uv + dy, AO_Depth( uv + dy ) );
	vec3 n = normalize( cross( AO_PickDerivative( c, l, r ), AO_PickDerivative( c, d, u ) ) );
	return ( dot( n, c ) > 0.0 ) ? -n : n;
}

float AO_Noise( vec2 p ) {
	return fract( 52.9829189 * fract( dot( p, vec2( 0.06711056, 0.00583715 ) ) ) );
}

float AO_Arc( float h, float n, float cosN, float sinN ) {
	return ( cosN + 2.0 * h * sinN - cos( 2.0 * h - n ) ) * 0.25;
}

float AO_Horizon( float hc, float low, vec2 suv, vec3 pos, vec3 v, float fMul, float fAdd, float thick ) {
	float sd = AO_Depth( suv );
	if ( sd >= 0.99999 ) {
		return hc;
	}
	vec3 delta = AO_ViewPos( suv, sd ) - pos;
	float dist = length( delta );
	if ( dist < 0.0001 ) {
		return hc;
	}
	float w = clamp( dist * fMul + fAdd, 0.0, 1.0 );
	w *= 1.0 - smoothstep( thick, 2.0 * thick, delta.z );
	return max( hc, mix( low, dot( delta / dist, v ), w ) );
}

// Returns visibility 0..1 (1 = fully open) for the current fragment.
float AO_Visibility() {
	if ( uDepthInfo.w <= 0.5 ) {
		return 1.0;
	}
	vec2 texel = uDepthInfo.xy;
	vec2 uv = ( gl_FragCoord.xy - uDepthViewport.xy ) * texel;
	if ( uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0 ) {
		return 1.0;
	}
	float depth = AO_Depth( uv );
	if ( depth >= 0.99999 ) {
		return 1.0;
	}

	vec3 c = AO_ViewPos( uv, depth );
	vec3 normal = AO_Normal( uv, c, texel );
	vec3 pos = c + normal * 0.5;
	vec3 v = normalize( -pos );
	float viewDepth = -c.z;

	float projScale = 0.5 * AO_P5() / texel.y;
	float radiusPixels = min( kAORadius * projScale / max( viewDepth, 1.0 ), 256.0 );
	if ( radiusPixels < 1.0 ) {
		return 1.0;
	}

	float fRange = 0.615 * kAORadius;
	float fMul = -1.0 / fRange;
	float fAdd = ( kAORadius - fRange ) / fRange + 1.0;
	float thick = kAOThickness * kAORadius;

	// per-frame seed from the TAA projection jitter (0 without TAA)
	vec2 jitterPx = vec2( AO_P8(), AO_P9() ) / ( 2.0 * texel );
	float seed = fract( sin( dot( jitterPx, vec2( 12.9898, 78.233 ) ) ) * 43758.5453 );
	float sliceNoise = fract( AO_Noise( gl_FragCoord.xy ) + seed );
	float stepNoise = fract( AO_Noise( gl_FragCoord.xy + vec2( 5.588238 ) ) + fract( seed * 1.618034 ) );

	float vis = 0.0;
	for ( int s = 0; s < kAOSlices; ++s ) {
		float phi = ( float( s ) + sliceNoise ) * ( kAOPi / float( kAOSlices ) );
		vec2 dir2 = vec2( cos( phi ), sin( phi ) );
		vec3 dir3 = vec3( dir2, 0.0 );
		vec3 ortho = dir3 - dot( dir3, v ) * v;
		vec3 axis = normalize( cross( dir3, v ) );
		vec3 pn = normal - axis * dot( normal, axis );
		float pl = length( pn );
		if ( pl < 0.0001 ) {
			vis += 1.0;
			continue;
		}
		float cosN = clamp( dot( pn, v ) / pl, -1.0, 1.0 );
		float n = sign( dot( ortho, pn ) ) * acos( cosN );
		float sinN = sin( n );
		float lowP = cos( n + kAOHalfPi );
		float lowN = cos( n - kAOHalfPi );
		float hP = lowP;
		float hN = lowN;
		for ( int j = 0; j < kAOSteps; ++j ) {
			float t = ( float( j ) + stepNoise ) / float( kAOSteps );
			t *= t;
			vec2 off = dir2 * max( t * radiusPixels, float( j ) + 1.0 ) * texel;
			hP = AO_Horizon( hP, lowP, uv + off, pos, v, fMul, fAdd, thick );
			hN = AO_Horizon( hN, lowN, uv - off, pos, v, fMul, fAdd, thick );
		}
		float a1 = min( acos( clamp( hP, -1.0, 1.0 ) ), n + kAOHalfPi );
		float a0 = max( -acos( clamp( hN, -1.0, 1.0 ) ), n - kAOHalfPi );
		vis += pl * ( AO_Arc( a1, n, cosN, sinN ) + AO_Arc( a0, n, cosN, sinN ) );
	}
	return clamp( vis / float( kAOSlices ), 0.0, 1.0 );
}

// Multi-bounce fit from the GTAO paper: visibility x and albedo -> effective
// occlusion including light that bounced inside the occluded region.
vec3 AO_MultiBounce( float x, vec3 albedo ) {
	vec3 a = 2.0404 * albedo - 0.3324;
	vec3 b = -4.7951 * albedo + 0.6417;
	vec3 c = 2.7552 * albedo + 0.6903;
	return max( vec3( x ), ( ( x * a + b ) * x + c ) * x );
}


// Probes behind the receiving surface are mostly inside the object it belongs
// to. openQ4 places probes and traces their visibility against world brushes
// only, so probes end up inside big entity models (crashed ships, boulders,
// machines); from there the capture looks straight through the backfaces and
// records unobstructed light, which made those objects far too bright.
// This weight (as in DDGI) prefers probes in front of the surface.
//   kBackfaceStrength - 0 = stock behaviour, 1 = full backface rejection
const float kBackfaceStrength = 0.0;  // off: did not fix the over-bright models in game tests

float BackfaceWeight( vec3 geomNormal, vec3 probeToReceiverDir ) {
	float t = ( dot( -probeToReceiverDir, geomNormal ) + 1.0 ) * 0.5;
	return mix( 1.0, max( t * t, 0.02 ), kBackfaceStrength );
}

// Baked irradiance at receiverPos from the 8 surrounding probes. weight = sum of
// trilinear weights of probes that hold data (0 = every probe was invalid,
// e.g. all of them ended up inside solid geometry).
vec3 SampleGridIrradiance( vec3 receiverPos, vec3 worldNormal, vec2 octCoord, vec3 geomNormal, out float weight ) {
	float gridCoordX;
	float gridCoordY;
	float gridCoordZ;
	float fracX;
	float fracY;
	float fracZ;
	vec3 lightOrigin = receiverPos - uLightGridOrigin.xyz;
	ComputeGridAxis( lightOrigin.x, uLightGridSize.x, uLightGridBounds.x, gridCoordX, fracX );
	ComputeGridAxis( lightOrigin.y, uLightGridSize.y, uLightGridBounds.y, gridCoordY, fracY );
	ComputeGridAxis( lightOrigin.z, uLightGridSize.z, uLightGridBounds.z, gridCoordZ, fracZ );

	vec3 irradiance = vec3( 0.0 );
	float validFactor = 0.0;
	float backfaceFactor = 0.0;

	for ( int i = 0; i < 8; i++ ) {
		float fi = float( i );
		vec3 corner = vec3(
			mod( fi, 2.0 ),
			mod( floor( fi * 0.5 ), 2.0 ),
			floor( fi * 0.25 ) );
		float factor =
			( corner.x > 0.0 ? fracX : 1.0 - fracX ) *
			( corner.y > 0.0 ? fracY : 1.0 - fracY ) *
			( corner.z > 0.0 ? fracZ : 1.0 - fracZ );
		if ( factor <= 0.0 ) {
			continue;
		}

		vec3 sampleCoord = vec3( gridCoordX, gridCoordY, gridCoordZ ) + corner;
		vec2 atlasCoord = ProbeAtlasCoord( sampleCoord, octCoord );

		vec3 sampleColor = DecodeBakedIrradiance( texture2D( uLightGridAtlas, atlasCoord ).rgb );
		if ( dot( sampleColor, vec3( 1.0 ) ) < 0.0001 ) {
			continue;
		}

		vec3 probePosition = ProbeWorldPosition( sampleCoord );
		vec3 probeToReceiver = receiverPos - probePosition;
		float receiverDistance = length( probeToReceiver );
		vec3 probeToReceiverDir = receiverDistance > 0.001 ? probeToReceiver / receiverDistance : worldNormal;
		vec2 visibilityOctCoord = ( OctEncode( probeToReceiverDir ) + vec2( 1.0 ) ) * 0.5;
		vec4 visibilityMoments = texture2D( uLightGridVisibilityAtlas, ProbeAtlasCoord( sampleCoord, visibilityOctCoord ) );
		float visibility = VisibilityWeight( visibilityMoments, receiverDistance, worldNormal, probeToReceiverDir );

		float backface = BackfaceWeight( geomNormal, probeToReceiverDir );
		irradiance += sampleColor * factor * visibility * backface;
		validFactor += factor;
		backfaceFactor += factor * backface;
	}

	if ( backfaceFactor > 0.0001 ) {
		irradiance *= 1.0 / backfaceFactor;
	}
	weight = validFactor;
	return irradiance;
}

void main() {
	if ( uDebugInfo.x > 5.5 && uDebugInfo.x < 6.5 ) {
		if ( uDepthInfo.w <= 0.5 ) {
			gl_FragColor = vec4( 0.0, 0.0, 0.6, 1.0 );
			return;
		}
		vec2 depthCoord = LightGridDepthCoord();
		if ( !LightGridDepthCoordValid( depthCoord ) ) {
			gl_FragColor = vec4( 0.8, 0.0, 0.8, 1.0 );
			return;
		}
		float sceneDepth = LightGridSceneDepth( depthCoord );
		bool accepted = gl_FragCoord.z <= sceneDepth + uDepthInfo.z;
		gl_FragColor = accepted ? vec4( 0.0, 0.6, 0.0, 1.0 ) : vec4( 0.7, 0.0, 0.0, 1.0 );
		return;
	}
	if ( uDebugInfo.x > 6.5 && uDebugInfo.x < 7.5 ) {
		if ( uDepthInfo.w <= 0.5 ) {
			gl_FragColor = vec4( 0.0, 0.0, 0.6, 1.0 );
			return;
		}
		vec2 depthCoord = LightGridDepthCoord();
		if ( !LightGridDepthCoordValid( depthCoord ) ) {
			gl_FragColor = vec4( 0.8, 0.0, 0.8, 1.0 );
			return;
		}
		float sceneDepth = LightGridSceneDepth( depthCoord );
		gl_FragColor = vec4( vec3( sceneDepth ), 1.0 );
		return;
	}

	if ( ( uDebugInfo.x > 0.5 && uDebugInfo.x < 1.5 ) || ( uDebugInfo.x > 2.5 && uDebugInfo.x < 3.5 ) ) {
		if ( uDebugInfo.x < 2.5 && !LightGridDepthAccepted() ) {
			discard;
		}
		gl_FragColor = vec4( uDebugInfo.yzw, 1.0 );
		return;
	}

	if ( !LightGridDepthAccepted() ) {
		discard;
	}

	vec4 bumpSample = texture2D( uBumpMap, vBumpTexCoord );
	vec3 localNormal = DecodeLocalNormal( bumpSample );
	vec3 worldNormal = SafeNormalize(
		vWorldTangent * localNormal.x +
		vWorldBitangent * localNormal.y +
		vWorldNormal * localNormal.z );

	vec2 octCoord = ( OctEncode( worldNormal ) + vec2( 1.0 ) ) * 0.5;

	vec3 geomNormal = SafeNormalize( vWorldNormal );
	float gridWeight = 0.0;
	vec3 irradiance = SampleGridIrradiance( vWorldPosition, worldNormal, octCoord, geomNormal, gridWeight );
	// No usable probe around this point (all 8 invalid): look for probes one and
	// two grid cells out along the surface normal, on the open side of the wall,
	// instead of leaving the surface pitch black.
	float fallbackStep = min( min( uLightGridSize.x, uLightGridSize.y ), uLightGridSize.z );  // one grid cell
	if ( gridWeight < 0.0001 ) {
		irradiance = SampleGridIrradiance( vWorldPosition + geomNormal * fallbackStep, worldNormal, octCoord, geomNormal, gridWeight );
	}
	if ( gridWeight < 0.0001 ) {
		irradiance = SampleGridIrradiance( vWorldPosition + geomNormal * ( 2.0 * fallbackStep ), worldNormal, octCoord, geomNormal, gridWeight );
	}

	irradiance = max( irradiance, vec3( uLightGridParams.y ) );

	vec3 diffuseSample = texture2D( uDiffuseMap, vDiffuseTexCoord ).rgb;
	diffuseSample = ApplyFlatDiffuseSweep( diffuseSample, vLocalZ );
	if ( uDebugInfo.x > 1.5 && uDebugInfo.x < 2.5 ) {
		gl_FragColor = vec4( ShapeLightGridContribution( irradiance * LightGridContributionScale() ), 1.0 );
		return;
	}
	if ( uDebugInfo.x > 3.5 && uDebugInfo.x < 4.5 ) {
		gl_FragColor = vec4( diffuseSample * uDiffuseColor.rgb * vVertexColor, 1.0 );
		return;
	}

	vec3 albedo = CapAlbedo( clamp( diffuseSample * uDiffuseColor.rgb * vVertexColor, 0.0, 1.0 ) );
	vec3 aoFactor = vec3( 1.0 );
	if ( uLightGridParams.x > 0.5 ) {
		float aoVisibility = AO_Visibility();
#if kMultiBounce
		aoFactor = AO_MultiBounce( aoVisibility, albedo );
#else
		aoFactor = vec3( aoVisibility );
#endif
	}
	vec3 diffuseLighting = ShapeLightGridContribution( irradiance * aoFactor * albedo * LightGridContributionScale() );
	if ( uDebugInfo.x > 4.5 && uDebugInfo.x < 5.5 ) {
		gl_FragColor = vec4( diffuseLighting, 1.0 );
		return;
	}
	gl_FragColor = vec4( diffuseLighting, 1.0 );
}

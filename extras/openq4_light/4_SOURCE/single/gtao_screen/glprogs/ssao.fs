#version 400 compatibility
#extension GL_ARB_derivative_control : enable
// GTAO (Ground Truth Ambient Occlusion, Jimenez et al. 2016) as a drop-in
// replacement for openQ4's glprogs/ssao.fs. Same inputs and uniforms as the
// stock shader, so the engine needs no changes.
//
// Single pass: the engine draws SSAO as one full-screen pass, so there is no
// separate blur pass. Instead the result is averaged over each 2x2 pixel quad
// (the GPU shades pixels in quads, and fine derivatives let a pixel read its
// quad neighbours), weighted by depth so it does not bleed across edges.
// This needs GL_ARB_derivative_control (any GL 4.5 GPU); without it the
// filter is skipped.
//
// How the engine cvars are used here:
//   r_ssaoRadius      - occlusion radius in world units (at kDistanceRefDepth
//                       from the camera when kDistanceScale > 0, see below)
//   r_ssaoSamples     - quality: slices = samples / 4 (2..8), 6 steps per side
//   r_ssaoIntensity   - strength: 1 = physically based GTAO, >1 darker
//   r_ssaoPower       - contrast curve: 1 = linear
//   r_ssaoBias        - pushes the centre point off the surface (world units)
//                       to stop flat surfaces darkening themselves
//   r_ssaoMaxDistance - fade out with distance (as before)
//   r_ssaoDebug 1     - show the AO mask only

uniform sampler2D Scene;
uniform sampler2D DepthBuffer;
uniform sampler2D FinalDepthBuffer;

uniform vec2 invTexSize;
uniform vec4 projectionInfo;
uniform vec2 depthProjection;
uniform float projectionScale;
uniform float ssaoRadius;
uniform float ssaoBias;
uniform float ssaoIntensity;
uniform float ssaoPower;
uniform float ssaoMaxDistance;
uniform float ssaoSampleCount;
uniform float ssaoDebugView;

// Radius growth with distance, like MXAO's "Increase Radius with Distance".
//   0.0 - fixed radius in world units (r_ssaoRadius): far objects get tiny,
//         fine-detail AO, near objects get wide AO
//   1.0 - fixed radius on screen: AO looks the same width at any distance,
//         far away it covers whole rooms instead of just seams
//   values in between blend the two
// At kDistanceRefDepth units from the camera both modes give the same radius.
const float kDistanceScale = 1.0;
const float kDistanceRefDepth = 64.0;

// Occluder thickness, as a fraction of the AO radius. A sample that is closer
// to the camera than the centre point by more than this is treated as a thin
// object standing in front (a pillar, a character, a railing) rather than a
// wall, and stops casting AO on what is far behind it. This removes the dark
// halos around silhouettes. 0 = off (every occluder infinitely thick),
// smaller = stricter.
const float kThickness = 0.5;

// 2x2 quad filter: 1 = on, 0 = off. kQuadSelfWeight is how much the pixel's
// own value counts against each of its three neighbours: 1 = plain average
// (least noise, visible 2x2 blocks), 2 = default compromise, 3+ = sharper.
#define QUAD_FILTER 1
const float kQuadSelfWeight = 2.0;

const float kPi = 3.14159265;
const float kHalfPi = 1.57079633;
const int kMaxSlices = 8;
const int kStepsPerSide = 6;

float SampleDepth( vec2 uv ) {
	return texture2D( DepthBuffer, uv ).x;
}

float SampleFinalDepth( vec2 uv ) {
	return texture2D( FinalDepthBuffer, uv ).x;
}

float ViewSpaceZFromDepth( float depth ) {
	float ndcDepth = depth * 2.0 - 1.0;
	float denom = ndcDepth + depthProjection.x;
	if ( abs( denom ) < 0.00001 ) {
		denom = ( denom < 0.0 ) ? -0.00001 : 0.00001;
	}
	return ( -depthProjection.y ) / denom;
}

vec3 ReconstructViewPosition( vec2 uv, float depth ) {
	float viewZ = ViewSpaceZFromDepth( depth );
	vec2 ndc = uv * 2.0 - 1.0;

	return vec3(
		-viewZ * ( ndc.x + projectionInfo.z ) * projectionInfo.x,
		-viewZ * ( ndc.y + projectionInfo.w ) * projectionInfo.y,
		viewZ );
}

vec3 PickBestDerivative( vec3 centerPos, vec3 negativePos, vec3 positivePos ) {
	vec3 negativeDelta = centerPos - negativePos;
	vec3 positiveDelta = positivePos - centerPos;
	return ( abs( negativeDelta.z ) < abs( positiveDelta.z ) ) ? negativeDelta : positiveDelta;
}

vec3 ReconstructNormal( vec2 uv, vec3 centerPos ) {
	vec2 offsetX = vec2( invTexSize.x, 0.0 );
	vec2 offsetY = vec2( 0.0, invTexSize.y );

	vec3 leftPos = ReconstructViewPosition( uv - offsetX, SampleDepth( uv - offsetX ) );
	vec3 rightPos = ReconstructViewPosition( uv + offsetX, SampleDepth( uv + offsetX ) );
	vec3 downPos = ReconstructViewPosition( uv - offsetY, SampleDepth( uv - offsetY ) );
	vec3 upPos = ReconstructViewPosition( uv + offsetY, SampleDepth( uv + offsetY ) );

	vec3 tangent = PickBestDerivative( centerPos, leftPos, rightPos );
	vec3 bitangent = PickBestDerivative( centerPos, downPos, upPos );
	vec3 normal = normalize( cross( tangent, bitangent ) );
	if ( dot( normal, centerPos ) > 0.0 ) {
		normal = -normal;
	}
	return normal;
}

float InterleavedGradientNoise( vec2 pixelPos ) {
	return fract( 52.9829189 * fract( dot( pixelPos, vec2( 0.06711056, 0.00583715 ) ) ) );
}

// Cosine-weighted visible arc for one side of a slice, from the GTAO paper.
float IntegrateArc( float h, float n, float cosN, float sinN ) {
	return ( cosN + 2.0 * h * sinN - cos( 2.0 * h - n ) ) * 0.25;
}

// Raises the horizon on one side of the slice with one depth sample.
float UpdateHorizon( float horizonCos, float lowCos, vec2 sampleUv, vec3 centerPos, vec3 viewDir,
		float falloffMul, float falloffAdd, float thickness ) {
	float sampleDepth = SampleDepth( sampleUv );
	if ( sampleDepth >= 0.99999 ) {
		return horizonCos;
	}
	vec3 delta = ReconstructViewPosition( sampleUv, sampleDepth ) - centerPos;
	float dist = length( delta );
	if ( dist < 0.0001 ) {
		return horizonCos;
	}
	float sampleCos = dot( delta / dist, viewDir );
	// Distant occluders fade back to the "no occluder" horizon.
	float weight = clamp( dist * falloffMul + falloffAdd, 0.0, 1.0 );
	// Thin-occluder limit: delta.z > 0 means the sample is nearer the camera.
	if ( thickness > 0.0 ) {
		weight *= 1.0 - smoothstep( thickness, 2.0 * thickness, delta.z );
	}
	return max( horizonCos, mix( lowCos, sampleCos, weight ) );
}

float ComputeAmbientOcclusion( vec2 uv, vec3 centerPos, vec3 centerNormal ) {
	float viewDepth = -centerPos.z;
	float fade = 1.0 - smoothstep( ssaoMaxDistance * 0.5, ssaoMaxDistance, viewDepth );
	if ( fade <= 0.0 ) {
		return 1.0;
	}

	vec3 pos = centerPos + centerNormal * ssaoBias * 0.25;
	vec3 viewDir = normalize( -pos );

	float worldRadius = ssaoRadius * mix( 1.0, max( viewDepth, 1.0 ) / kDistanceRefDepth, kDistanceScale );
	float radiusPixels = worldRadius * projectionScale / max( viewDepth, 1.0 );
	if ( radiusPixels < 1.0 ) {
		return 1.0;
	}
	radiusPixels = min( radiusPixels, 256.0 );

	// Occluders start fading at ~40% of the radius and are ignored at the radius.
	float falloffRange = 0.615 * worldRadius;
	float falloffFrom = worldRadius - falloffRange;
	float falloffMul = -1.0 / falloffRange;
	float falloffAdd = falloffFrom / falloffRange + 1.0;
	float thickness = kThickness * worldRadius;

	float sliceCount = clamp( floor( ssaoSampleCount / 4.0 ), 2.0, float( kMaxSlices ) );

	vec2 pixelPos = uv / invTexSize;

	// Per-frame noise seed. With r_temporalAA 1 the engine shifts the projection
	// by a different sub-pixel amount every frame, and that shift is in
	// projectionInfo.zw. Turning it into a seed makes the noise pattern change
	// every frame so TAA can average it out. Without TAA the shift is zero,
	// the seed is zero and the pattern stays fixed as before.
	vec2 jitterPx = projectionInfo.zw / ( 2.0 * invTexSize );
	float frameSeed = fract( sin( dot( jitterPx, vec2( 12.9898, 78.233 ) ) ) * 43758.5453 );

	float sliceNoise = fract( InterleavedGradientNoise( pixelPos ) + frameSeed );
	float stepNoise = fract( InterleavedGradientNoise( pixelPos + vec2( 5.588238, 5.588238 ) ) + fract( frameSeed * 1.6180340 ) );

	float visibility = 0.0;

	for ( int s = 0; s < kMaxSlices; ++s ) {
		if ( float( s ) >= sliceCount ) {
			break;
		}

		float phi = ( float( s ) + sliceNoise ) * ( kPi / sliceCount );
		vec2 dir2 = vec2( cos( phi ), sin( phi ) );
		vec3 dir3 = vec3( dir2, 0.0 );

		// Slice plane: spanned by the view direction and the screen direction.
		vec3 orthoDir = dir3 - dot( dir3, viewDir ) * viewDir;
		vec3 axis = normalize( cross( dir3, viewDir ) );
		vec3 projNormal = centerNormal - axis * dot( centerNormal, axis );
		float projNormalLen = length( projNormal );
		if ( projNormalLen < 0.0001 ) {
			visibility += 1.0;
			continue;
		}

		float cosN = clamp( dot( projNormal, viewDir ) / projNormalLen, -1.0, 1.0 );
		float n = sign( dot( orthoDir, projNormal ) ) * acos( cosN );
		float sinN = sin( n );

		// Lowest possible horizons: the surface tangent on each side.
		float lowCosPos = cos( n + kHalfPi );
		float lowCosNeg = cos( n - kHalfPi );
		float horizonCosPos = lowCosPos;
		float horizonCosNeg = lowCosNeg;

		for ( int j = 0; j < kStepsPerSide; ++j ) {
			float t = ( float( j ) + stepNoise ) / float( kStepsPerSide );
			t *= t;	// denser near the centre, where contact detail is
			vec2 offset = dir2 * max( t * radiusPixels, float( j ) + 1.0 ) * invTexSize;

			horizonCosPos = UpdateHorizon( horizonCosPos, lowCosPos, uv + offset, pos, viewDir, falloffMul, falloffAdd, thickness );
			horizonCosNeg = UpdateHorizon( horizonCosNeg, lowCosNeg, uv - offset, pos, viewDir, falloffMul, falloffAdd, thickness );
		}

		// Horizon angles from the view direction, clamped to the hemisphere.
		float hPos = min( acos( clamp( horizonCosPos, -1.0, 1.0 ) ), n + kHalfPi );
		float hNeg = max( -acos( clamp( horizonCosNeg, -1.0, 1.0 ) ), n - kHalfPi );

		visibility += projNormalLen * ( IntegrateArc( hPos, n, cosN, sinN ) + IntegrateArc( hNeg, n, cosN, sinN ) );
	}

	float ao = clamp( visibility / sliceCount, 0.0, 1.0 );
	ao = pow( ao, max( ssaoPower, 0.001 ) );
	ao = clamp( 1.0 - ( 1.0 - ao ) * ssaoIntensity, 0.0, 1.0 );
	return mix( 1.0, ao, fade );
}

bool PixelIsForeground( vec2 uv, float sourceDepth ) {
	float finalDepth = SampleFinalDepth( uv );
	if ( finalDepth >= 0.99999 || sourceDepth >= 0.99999 ) {
		return false;
	}

	float sourceViewDepth = -ViewSpaceZFromDepth( sourceDepth );
	float finalViewDepth = -ViewSpaceZFromDepth( finalDepth );
	return finalViewDepth + 1.0 < sourceViewDepth;
}

#if QUAD_FILTER && defined( GL_ARB_derivative_control )
// Reads value v from the quad neighbour along x / y. With fine derivatives,
// dFdxFine(v) is exactly (right pixel - left pixel) of this pixel's pair.
float QuadNeighbourX( float v, float sx ) { return v + sx * dFdxFine( v ); }
float QuadNeighbourY( float v, float sy ) { return v + sy * dFdyFine( v ); }

// Depth-aware 2x2 average. Called by every pixel of the quad (no early exits
// before it), otherwise the derivatives are undefined.
float QuadFilter( float ao, float viewDepth, float valid ) {
	// +1 if the neighbour is to the right / above, -1 if to the left / below.
	float sx = ( mod( floor( gl_FragCoord.x ), 2.0 ) < 0.5 ) ? 1.0 : -1.0;
	float sy = ( mod( floor( gl_FragCoord.y ), 2.0 ) < 0.5 ) ? 1.0 : -1.0;

	float aoX = QuadNeighbourX( ao, sx );
	float aoY = QuadNeighbourY( ao, sy );
	float aoXY = QuadNeighbourY( aoX, sy );
	float dX = QuadNeighbourX( viewDepth, sx );
	float dY = QuadNeighbourY( viewDepth, sy );
	float dXY = QuadNeighbourY( dX, sy );
	float vX = QuadNeighbourX( valid, sx );
	float vY = QuadNeighbourY( valid, sy );
	float vXY = QuadNeighbourY( vX, sy );

	// Neighbours more than ~2% of the distance away in depth are another
	// surface and get (almost) no weight.
	float tolerance = max( viewDepth * 0.02, 1.0 );
	float wX = vX * clamp( 1.0 - abs( dX - viewDepth ) / tolerance, 0.0, 1.0 );
	float wY = vY * clamp( 1.0 - abs( dY - viewDepth ) / tolerance, 0.0, 1.0 );
	float wXY = vXY * clamp( 1.0 - abs( dXY - viewDepth ) / tolerance, 0.0, 1.0 );

	return ( ao * kQuadSelfWeight + aoX * wX + aoY * wY + aoXY * wXY ) / ( kQuadSelfWeight + wX + wY + wXY );
}
#endif

void main() {
	vec2 uv = gl_TexCoord[0].st;
	vec4 scene = texture2D( Scene, uv );
	float depth = SampleDepth( uv );

	// No early returns: the quad filter below needs all four pixels.
	bool sky = depth >= 0.99999;
	bool foreground = !sky && PixelIsForeground( uv, depth );
	float valid = ( sky || foreground ) ? 0.0 : 1.0;

	float ao = 1.0;
	float viewDepth = 0.0;
	if ( valid > 0.5 ) {
		vec3 centerPos = ReconstructViewPosition( uv, depth );
		vec3 centerNormal = ReconstructNormal( uv, centerPos );
		viewDepth = -centerPos.z;
		ao = ComputeAmbientOcclusion( uv, centerPos, centerNormal );
	}

#if QUAD_FILTER && defined( GL_ARB_derivative_control )
	float filtered = QuadFilter( ao, viewDepth, valid );
	if ( valid > 0.5 ) {
		ao = filtered;
	}
#endif

	if ( ssaoDebugView > 0.5 ) {
		gl_FragColor = sky ? scene : vec4( vec3( ao ), scene.a );
		return;
	}

	gl_FragColor = vec4( scene.rgb * ao, scene.a );
}

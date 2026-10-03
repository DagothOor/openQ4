// Depth dump for openQ4: replaces glprogs/ssao.fs ONLY while capturing.
// With r_ssao 1 and r_ssaoDebug 1 the frame shows the depth buffer encoded
// as colours; a TGA screenshot of it can be decoded back into depth.
// Without r_ssaoDebug the scene passes through untouched (no AO at all).
//
// Layout (rows counted from the top of the 3D view):
//   rows 0-7    calibration ramp: column x (0..255) = grey level x/255,
//               lets the decoder undo gamma/brightness applied after this pass
//   rows 8-15   header: 8-pixel cells, each an 18-bit number (see Encode18):
//               cell 0 = 1/P[0] * 16384, cell 1 = 1/P[5] * 16384,
//               cell 2 = magic 0x2A2A5 (layout check),
//               cell 3 = (P[8] + 1) * 65536, cell 4 = (P[9] + 1) * 65536
//   everywhere else: view depth in units * 64 as an 18-bit number;
//               0 = weapon / foreground, 262143 = sky
// Each 18-bit number is split into three 6-bit digits (R high, G mid, B low)
// stored at the centre of their 4-level bins, so mild colour changes after
// this pass do not flip digits.

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

float ViewSpaceZFromDepth( float depth ) {
	float ndcDepth = depth * 2.0 - 1.0;
	float denom = ndcDepth + depthProjection.x;
	if ( abs( denom ) < 0.00001 ) {
		denom = ( denom < 0.0 ) ? -0.00001 : 0.00001;
	}
	return ( -depthProjection.y ) / denom;
}

vec3 Encode18( float value ) {
	float q = clamp( floor( value + 0.5 ), 0.0, 262143.0 );
	float hi = floor( q / 4096.0 );
	float mid = floor( ( q - hi * 4096.0 ) / 64.0 );
	float lo = q - hi * 4096.0 - mid * 64.0;
	return ( vec3( hi, mid, lo ) * 4.0 + 2.0 ) / 255.0;
}

bool PixelIsForeground( vec2 uv, float sourceDepth ) {
	float finalDepth = texture2D( FinalDepthBuffer, uv ).x;
	if ( finalDepth >= 0.99999 || sourceDepth >= 0.99999 ) {
		return false;
	}
	float sourceViewDepth = -ViewSpaceZFromDepth( sourceDepth );
	float finalViewDepth = -ViewSpaceZFromDepth( finalDepth );
	return finalViewDepth + 1.0 < sourceViewDepth;
}

void main() {
	vec2 uv = gl_TexCoord[0].st;
	vec4 scene = texture2D( Scene, uv );

	if ( ssaoDebugView < 0.5 ) {
		gl_FragColor = scene;
		return;
	}

	vec2 viewSize = floor( 1.0 / invTexSize + 0.5 );
	vec2 pixel = floor( uv * viewSize );
	float rowFromTop = viewSize.y - 1.0 - pixel.y;

	if ( rowFromTop < 8.0 && pixel.x < 256.0 ) {
		gl_FragColor = vec4( vec3( pixel.x / 255.0 ), 1.0 );
		return;
	}
	if ( rowFromTop >= 8.0 && rowFromTop < 16.0 && pixel.x < 40.0 ) {
		float cell = floor( pixel.x / 8.0 );
		float value = 0.0;
		if ( cell < 0.5 ) {
			value = projectionInfo.x * 16384.0;
		} else if ( cell < 1.5 ) {
			value = projectionInfo.y * 16384.0;
		} else if ( cell < 2.5 ) {
			value = 172709.0;	// 0x2A2A5
		} else if ( cell < 3.5 ) {
			value = ( projectionInfo.z + 1.0 ) * 65536.0;
		} else {
			value = ( projectionInfo.w + 1.0 ) * 65536.0;
		}
		gl_FragColor = vec4( Encode18( value ), 1.0 );
		return;
	}

	float depth = texture2D( DepthBuffer, uv ).x;
	float code;
	if ( depth >= 0.99999 ) {
		code = 262143.0;
	} else if ( PixelIsForeground( uv, depth ) ) {
		code = 0.0;
	} else {
		code = max( -ViewSpaceZFromDepth( depth ) * 64.0, 1.0 );
	}
	gl_FragColor = vec4( Encode18( code ), 1.0 );
}

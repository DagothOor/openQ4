// Copyright (C) 2026 DarkMatter Productions
#include "../../../src/framework/VRMathCore.h"
#include <cstdio>
#include <cstdlib>
#include <limits>

static void Check( bool condition, const char *message ) {
	if ( !condition ) {
		std::fprintf( stderr, "VR math: %s\n", message );
		std::exit( 1 );
	}
}

static bool Near( float a, float b, float tolerance = 0.0001f ) {
	return std::fabs( a - b ) <= tolerance;
}

static bool NearVec( const vrVec3_t &a, const vrVec3_t &b, float tolerance = 0.0001f ) {
	return Near( a.x, b.x, tolerance ) && Near( a.y, b.y, tolerance ) && Near( a.z, b.z, tolerance );
}

static vrQuat_t AxisAngle( const vrVec3_t &axis, float degrees ) {
	const float half = degrees * VR_DEG2RAD * 0.5f;
	const float s = std::sin( half );
	vrQuat_t q = { axis.x * s, axis.y * s, axis.z * s, std::cos( half ) };
	return q;
}

static void TestBasis( void ) {
	Check( NearVec( VR_XrToEngineDirection( VR_Vec3( 0, 0, -1 ) ), VR_Vec3( 1, 0, 0 ) ), "OpenXR forward is engine +X" );
	Check( NearVec( VR_XrToEngineDirection( VR_Vec3( 1, 0, 0 ) ), VR_Vec3( 0, -1, 0 ) ), "OpenXR right is engine -Y" );
	Check( NearVec( VR_XrToEngineDirection( VR_Vec3( 0, 1, 0 ) ), VR_Vec3( 0, 0, 1 ) ), "OpenXR up is engine +Z" );
	const vrVec3_t sample = VR_Vec3( 0.25f, -1.5f, 3.0f );
	Check( NearVec( VR_EngineToXrDirection( VR_XrToEngineDirection( sample ) ), sample ), "direction round trip" );
	Check( NearVec( VR_XrToEnginePosition( VR_Vec3( 0, 1.7f, 0 ), 40.0f ), VR_Vec3( 0, 0, 68.0f ) ), "standing eye height scales to units" );
}

static void TestOrientation( void ) {
	// Turning the head 90 degrees to the left in OpenXR is a positive rotation
	// about +Y; the engine sees the same turn as +90 yaw.
	const vrQuat_t left = VR_XrToEngineOrientation( AxisAngle( VR_Vec3( 0, 1, 0 ), 90.0f ) );
	Check( Near( VR_QuatYawDegrees( left ), 90.0f, 0.01f ), "left turn is positive engine yaw" );
	vrVec3_t axis[3];
	VR_QuatToAxis( left, axis );
	Check( NearVec( axis[0], VR_Vec3( 0, 1, 0 ) ), "turned forward faces the old left" );
	Check( NearVec( axis[2], VR_Vec3( 0, 0, 1 ) ), "yaw keeps up" );

	// Looking up 30 degrees is a positive rotation about OpenXR +X and a
	// negative engine pitch.
	const vrQuat_t up = VR_XrToEngineOrientation( AxisAngle( VR_Vec3( 1, 0, 0 ), 30.0f ) );
	VR_QuatToAxis( up, axis );
	Check( Near( VR_PitchDegrees( axis[0] ), -30.0f, 0.01f ), "looking up is negative engine pitch" );
	Check( Near( VR_YawDegrees( axis[0] ), 0.0f, 0.01f ), "looking up keeps yaw" );

	const vrQuat_t sample = VR_QuatNormalize( AxisAngle( VR_Vec3( 0.3f, 0.8f, -0.52f ), 47.0f ) );
	const vrQuat_t back = VR_EngineToXrOrientation( VR_XrToEngineOrientation( sample ) );
	Check( Near( back.x, sample.x ) && Near( back.y, sample.y ) && Near( back.z, sample.z ) && Near( back.w, sample.w ),
		"orientation round trip" );

	// The converted quaternion rotates converted vectors exactly as the
	// original rotates the originals.
	const vrVec3_t v = VR_Vec3( 0.2f, -0.7f, 0.4f );
	const vrVec3_t expected = VR_XrToEngineDirection( VR_RotateVector( sample, v ) );
	const vrVec3_t actual = VR_RotateVector( VR_XrToEngineOrientation( sample ), VR_XrToEngineDirection( v ) );
	Check( NearVec( expected, actual ), "conversion commutes with rotation" );

	const vrQuat_t nan = { std::numeric_limits<float>::quiet_NaN(), 0.0f, 0.0f, 1.0f };
	const vrQuat_t safe = VR_QuatNormalize( nan );
	Check( safe.x == 0.0f && safe.y == 0.0f && safe.z == 0.0f && safe.w == 1.0f, "non-finite orientation becomes identity" );
	const vrQuat_t zero = { 0.0f, 0.0f, 0.0f, 0.0f };
	Check( VR_QuatNormalize( zero ).w == 1.0f, "zero orientation becomes identity" );

	Check( Near( VR_NormalizeDegrees180( 190.0f ), -170.0f ), "wrap above 180" );
	Check( Near( VR_NormalizeDegrees180( -540.0f ), -180.0f ), "wrap far below" );
	Check( VR_NormalizeDegrees180( std::numeric_limits<float>::infinity() ) == 0.0f, "non-finite angle wraps to zero" );
}

static void TestProjection( void ) {
	const vrFovTangents_t symmetric = VR_FovTangentsFromAngles( -45.0f * VR_DEG2RAD, 45.0f * VR_DEG2RAD, 45.0f * VR_DEG2RAD, -45.0f * VR_DEG2RAD );
	Check( VR_FovTangentsValid( symmetric ), "symmetric frustum is valid" );
	float xmin, xmax, ymin, ymax;
	VR_ProjectionExtents( symmetric, 3.0f, xmin, xmax, ymin, ymax );
	Check( Near( xmin, -3.0f ) && Near( xmax, 3.0f ) && Near( ymin, -3.0f ) && Near( ymax, 3.0f ), "90 degree extents equal the near distance" );

	// A typical left eye: more field towards the nose side is narrower.
	const vrFovTangents_t eye = VR_FovTangentsFromAngles( -0.94f, 0.75f, 0.84f, -0.90f );
	Check( VR_FovTangentsValid( eye ), "off-axis eye is valid" );
	float fovX, fovY;
	VR_EnclosingFovDegrees( eye, fovX, fovY );
	Check( Near( fovX, 2.0f * 0.94f * VR_RAD2DEG, 0.01f ), "enclosing horizontal field uses the wider side" );
	Check( Near( fovY, 2.0f * 0.90f * VR_RAD2DEG, 0.01f ), "enclosing vertical field uses the wider side" );

	vrFovTangents_t inverted = eye;
	inverted.left = eye.right;
	inverted.right = eye.left;
	Check( !VR_FovTangentsValid( inverted ), "inverted frustum rejected" );
	vrFovTangents_t broken = eye;
	broken.up = std::numeric_limits<float>::quiet_NaN();
	Check( !VR_FovTangentsValid( broken ), "non-finite frustum rejected" );
	vrFovTangents_t degenerate = eye;
	degenerate.right = 1000.0f;
	Check( !VR_FovTangentsValid( degenerate ), "near-90 degree frustum rejected" );
}

static void TestEyeImage( void ) {
	const vrFovTangents_t symmetric = VR_FovTangentsFromAngles( -45.0f * VR_DEG2RAD, 45.0f * VR_DEG2RAD, 45.0f * VR_DEG2RAD, -45.0f * VR_DEG2RAD );
	float u, v;
	const vrEyeTangent_t ahead = VR_EyeTangentOf( VR_Vec3( 10.0f, 0.0f, 0.0f ) );
	Check( ahead.inFront && Near( ahead.x, 0.0f ) && Near( ahead.y, 0.0f ) && Near( ahead.depth, 10.0f ), "a point dead ahead lies on the view axis" );
	VR_TangentToImage( symmetric, ahead.x, ahead.y, u, v );
	Check( Near( u, 0.5f ) && Near( v, 0.5f ), "the view axis is the centre of a symmetric image" );
	const vrEyeTangent_t corner = VR_EyeTangentOf( VR_Vec3( 2.0f, -2.0f, 2.0f ) );
	VR_TangentToImage( symmetric, corner.x, corner.y, u, v );
	Check( Near( u, 1.0f ) && Near( v, 0.0f ), "45 degrees right and up is the top right corner" );

	const vrFovTangents_t eye = { -1.2f, 0.8f, 1.0f, -1.0f };
	VR_TangentToImage( eye, 0.0f, 0.0f, u, v );
	Check( Near( u, 0.6f ) && Near( v, 0.5f ), "an off-axis eye's view axis sits off the image centre" );

	Check( !VR_EyeTangentOf( VR_Vec3( -1.0f, 0.0f, 0.0f ) ).inFront, "a point behind the eye does not project" );
	Check( !VR_EyeTangentOf( VR_Vec3( 0.0f, 1.0f, 0.0f ) ).inFront, "a point on the eye plane does not project" );
	Check( !VR_EyeTangentOf( VR_Vec3( std::numeric_limits<float>::quiet_NaN(), 0.0f, 0.0f ) ).inFront, "a non-finite point does not project" );

	// Eyes 64 units apart (the left one on +Y) both see a point 1000 units
	// ahead of their midpoint; its disparity gives back that depth.
	const float ipd = 64.0f;
	const float depth = 1000.0f;
	const vrEyeTangent_t fromLeft = VR_EyeTangentOf( VR_Vec3( depth, -ipd * 0.5f, 0.0f ) );
	const vrEyeTangent_t fromRight = VR_EyeTangentOf( VR_Vec3( depth, ipd * 0.5f, 0.0f ) );
	Check( fromLeft.x > fromRight.x, "the left eye sees a point further right than the right eye does" );
	Check( Near( ipd / ( fromLeft.x - fromRight.x ), depth, 0.01f ), "disparity gives back the point's depth" );
}

static void TestTurning( void ) {
	vrSnapTurnState_t snap = { false };
	Check( VR_SnapTurn( snap, 0.5f, 45.0f ) == 0.0f, "below the press threshold does nothing" );
	Check( VR_SnapTurn( snap, 0.9f, 45.0f ) == -45.0f, "pushing right turns right once" );
	Check( VR_SnapTurn( snap, 1.0f, 45.0f ) == 0.0f, "holding does not repeat" );
	Check( VR_SnapTurn( snap, 0.5f, 45.0f ) == 0.0f, "hysteresis keeps the latch" );
	Check( VR_SnapTurn( snap, 0.1f, 45.0f ) == 0.0f, "release re-arms" );
	Check( VR_SnapTurn( snap, -0.95f, 30.0f ) == 30.0f, "pushing left turns left" );
	Check( VR_SnapTurn( snap, std::numeric_limits<float>::quiet_NaN(), 30.0f ) == 0.0f, "non-finite stick ignored" );

	Check( VR_SmoothTurn( 0.1f, 120.0f, 0.5f, 0.2f ) == 0.0f, "deadzone swallows drift" );
	Check( Near( VR_SmoothTurn( 1.0f, 120.0f, 0.5f, 0.2f ), -60.0f ), "full right deflection turns right at speed" );
	Check( Near( VR_SmoothTurn( -0.6f, 100.0f, 1.0f, 0.2f ), 50.0f ), "partial left deflection rescales past the deadzone" );
	Check( VR_SmoothTurn( 1.0f, 120.0f, -1.0f, 0.2f ) == 0.0f, "negative time step ignored" );
}

static void TestOffsets( void ) {
	const vrVec3_t inside = VR_ClampHorizontalOffset( VR_Vec3( 3.0f, 4.0f, 9.0f ), 10.0f );
	Check( NearVec( inside, VR_Vec3( 3.0f, 4.0f, 9.0f ) ), "small offsets pass" );
	const vrVec3_t outside = VR_ClampHorizontalOffset( VR_Vec3( 30.0f, 40.0f, -6.0f ), 10.0f );
	Check( NearVec( outside, VR_Vec3( 6.0f, 8.0f, -6.0f ) ), "horizontal clamp keeps direction and height" );
	const vrVec3_t broken = VR_ClampHorizontalOffset( VR_Vec3( std::numeric_limits<float>::infinity(), 0.0f, 0.0f ), 10.0f );
	Check( NearVec( broken, VR_Vec3( 0.0f, 0.0f, 0.0f ) ), "non-finite offset collapses" );

	vrVec3_t position;
	vrQuat_t orientation;
	VR_ComposeWorldPose( VR_Vec3( 100.0f, 200.0f, 64.0f ), 90.0f, VR_Vec3( 10.0f, 0.0f, 2.0f ), VR_QuatIdentity(), position, orientation );
	Check( NearVec( position, VR_Vec3( 100.0f, 210.0f, 66.0f ) ), "body yaw rotates the tracked offset" );
	Check( Near( VR_QuatYawDegrees( orientation ), 90.0f, 0.01f ), "body yaw rotates the orientation" );
	VR_ComposeWorldPose( VR_Vec3( 0.0f, 0.0f, 0.0f ), 30.0f, VR_Vec3( 0.0f, 0.0f, 0.0f ), VR_YawQuat( 15.0f ), position, orientation );
	Check( Near( VR_QuatYawDegrees( orientation ), 45.0f, 0.01f ), "head yaw adds to body yaw" );
}

static void TestQuad( void ) {
	const vrVec3_t center = VR_Vec3( 0.0f, 0.0f, -2.0f );
	const vrQuat_t facing = VR_QuatIdentity();
	vrQuadHit_t hit = VR_RayQuadIntersect( VR_Vec3( 0, 0, 0 ), VR_Vec3( 0, 0, -1 ), center, facing, 2.0f, 1.5f );
	Check( hit.hit && Near( hit.u, 0.5f ) && Near( hit.v, 0.5f ) && Near( hit.distance, 2.0f ), "centre hit" );
	hit = VR_RayQuadIntersect( VR_Vec3( -0.5f, 0.375f, 0.0f ), VR_Vec3( 0, 0, -1 ), center, facing, 2.0f, 1.5f );
	Check( hit.hit && Near( hit.u, 0.25f ) && Near( hit.v, 0.25f ), "upper-left quadrant maps to small u and v" );
	hit = VR_RayQuadIntersect( VR_Vec3( 1.5f, 0.0f, 0.0f ), VR_Vec3( 0, 0, -1 ), center, facing, 2.0f, 1.5f );
	Check( !hit.hit, "outside the quad misses" );
	hit = VR_RayQuadIntersect( VR_Vec3( 0, 0, -4.0f ), VR_Vec3( 0, 0, 1 ), center, facing, 2.0f, 1.5f );
	Check( !hit.hit, "the back face does not take input" );
	hit = VR_RayQuadIntersect( VR_Vec3( 0, 0, 0 ), VR_Vec3( 0, 0, 1 ), center, facing, 2.0f, 1.5f );
	Check( !hit.hit, "pointing away misses" );
	// a quad turned 90 degrees to the right of the viewer
	const vrQuat_t turned = AxisAngle( VR_Vec3( 0, 1, 0 ), -90.0f );
	hit = VR_RayQuadIntersect( VR_Vec3( 0, 0, 0 ), VR_Vec3( 1, 0, 0 ), VR_Vec3( 3.0f, 0.0f, 0.0f ), turned, 2.0f, 1.5f );
	Check( hit.hit && Near( hit.u, 0.5f ) && Near( hit.v, 0.5f ) && Near( hit.distance, 3.0f ), "rotated quad centre hit" );
}

int main() {
	TestBasis();
	TestOrientation();
	TestProjection();
	TestEyeImage();
	TestTurning();
	TestOffsets();
	TestQuad();
	std::printf( "VR math core: all checks passed\n" );
	return 0;
}

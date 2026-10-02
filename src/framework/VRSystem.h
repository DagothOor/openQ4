// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#ifndef __VRSYSTEM_H__
#define __VRSYSTEM_H__

/*
===============================================================================

	Virtual reality presentation and input.

	The engine owns the OpenXR session (src/sys/openxr) and brackets every
	presented screen update with BeginFrame/EndFrame. The renderer module
	presents into the session's swapchains (idRenderSystem::SetVRFrame and
	SetVRRenderTarget), and the game modules read the tracked poses below to
	build one view per eye. Builds without OpenXR, and dedicated servers, run
	the null implementation, which never activates.

	Everything here crosses the game-module boundary, so it stays POD apart
	from the idVec3/idMat3 members renderView_t already carries.
	See docs/dev/plans/2026-10-02-openxr-vr.md.

===============================================================================
*/

const int VR_NUM_EYES = 2;
const int VR_NUM_HANDS = 2;

typedef enum {
	VR_HAND_LEFT = 0,
	VR_HAND_RIGHT = 1
} vrHand_t;

typedef enum {
	VR_AIM_HEAD = 0,		// gaze aim: the usercmd follows the head
	VR_AIM_HAND = 1			// the weapon hand's controller aims
} vrAimMode_t;

// A tracked pose relative to the recentred tracking origin, in engine axes
// (forward, left, up) and game units. The origin is where the player's eye
// sits when the head is at the recentre position.
typedef struct vrPose_s {
	bool					valid;
	idVec3					origin;
	idMat3					axis;		// rows: forward, left, up (renderView_t::viewaxis layout)
} vrPose_t;

// One eye: its pose and the half-angle tangents of its off-axis frustum
// (left and down negative), exactly as rendered and submitted.
typedef struct vrEyeView_s {
	vrPose_t				pose;
	float					tanLeft, tanRight, tanUp, tanDown;
} vrEyeView_t;

typedef struct vrFrameState_s {
	int						frameNumber;	// counts XR frames opened by the engine
	bool					active;			// a session is presenting to a headset this frame
	bool					stereo;			// eye targets exist: render the first-person 3D pass per eye
	bool					focused;		// the runtime routes controller input to openQ4
	vrPose_t				head;
	vrEyeView_t				eyes[VR_NUM_EYES];
	vrPose_t				grip[VR_NUM_HANDS];	// where the hand holds the controller
	vrPose_t				aim[VR_NUM_HANDS];	// the controller's pointing ray (+X forward)

	// The body's yaw in usercmd angle space. The world yaw of the tracking
	// space is bodyYaw + the player's deltaViewAngles yaw.
	float					bodyYaw;

	int						aimMode;		// vrAimMode_t
	int						weaponHand;		// vrHand_t
	float					unitsPerMetre;
	float					headOffsetLimit;	// horizontal head travel from the body, units

	// view-weapon placement in the weapon hand's aim axes (units, degrees)
	idVec3					weaponOffset;
	float					weaponPitch;
} vrFrameState_t;

// What the usercmd generator applies for one tic while VR drives input.
typedef struct vrUsercmdInput_s {
	float					aimYaw;			// absolute usercmd yaw, degrees (body yaw + local aim)
	float					aimPitch;		// usercmd pitch, degrees (positive looks down)
	float					forward;		// locomotion, -1..1, in the aim frame
	float					right;
} vrUsercmdInput_t;

class idVRSystem {
public:
	virtual					~idVRSystem( void ) {}

	// Registers commands; makes no OpenXR call.
	virtual void			Init( void ) = 0;
	virtual void			Shutdown( void ) = 0;

	// The renderer has a live device (after InitOpenGL and every vid_restart).
	// Starts a session when vr_enable is set.
	virtual void			RendererStarted( void ) = 0;
	// The renderer is about to destroy its device: the session and its
	// swapchains are torn down first.
	virtual void			RendererStopping( void ) = 0;

	// Bracket one presented screen update. While a session runs, BeginFrame
	// waits on the headset's frame timing, so it is also the frame pacer.
	virtual void			BeginFrame( void ) = 0;
	virtual void			EndFrame( void ) = 0;

	// True while the headset paces frames: com_maxfps and window vsync stand down.
	virtual bool			IsPacing( void ) const = 0;
	// True while a session presents.
	virtual bool			IsActive( void ) const = 0;

	// Pose and presentation state for the screen update in progress.
	virtual void			GetFrameState( vrFrameState_t &state ) const = 0;

	// Called by the usercmd generator (possibly on the async tic thread).
	// otherYawDelta is the yaw the mouse, keys or a gamepad turned this tic;
	// it turns the body. Returns false while VR does not drive input.
	virtual bool			GetUsercmdInput( float otherYawDelta, float currentYaw, vrUsercmdInput_t &input ) = 0;

	// Menus: marks where the controller points on the virtual screen. Called
	// once all 2D drawing is queued, before the renderer's EndFrame.
	virtual void			DrawMenuPointer( void ) = 0;
};

extern idVRSystem *			vrSystem;

/*
===============================================================================

	Placing tracked poses in the world (both game modules).

	The tracking origin sits at the player's eye and faces trackingYaw, the
	world yaw of the tracking space: vrFrameState_t::bodyYaw plus the
	player's deltaViewAngles yaw (the same mapping that turns usercmd angles
	into view angles). A tracked pose then lands at
	eyeOrigin + pose.origin * yaw, with axis pose.axis * yaw.

===============================================================================
*/

ID_INLINE idMat3 VR_TrackingAxis( float trackingYaw ) {
	return idAngles( 0.0f, trackingYaw, 0.0f ).ToMat3();
}

ID_INLINE void VR_PoseToWorld( const vrPose_t &pose, const idVec3 &eyeOrigin, float trackingYaw, idVec3 &origin, idMat3 &axis ) {
	const idMat3 tracking = VR_TrackingAxis( trackingYaw );
	origin = eyeOrigin + pose.origin * tracking;
	axis = pose.axis * tracking;
}

// Horizontal head travel past the limit is cancelled, so leaning walks the
// camera no further than the body's edge; height changes always pass.
ID_INLINE idVec3 VR_HeadOffsetCorrection( const vrFrameState_t &frame ) {
	if ( !frame.head.valid || frame.headOffsetLimit < 0.0f ) {
		return vec3_origin;
	}
	const idVec3 &head = frame.head.origin;
	const float radius = idMath::Sqrt( head.x * head.x + head.y * head.y );
	if ( radius <= frame.headOffsetLimit || radius <= 0.0f ) {
		return vec3_origin;
	}
	const float scale = ( radius - frame.headOffsetLimit ) / radius;
	return idVec3( -head.x * scale, -head.y * scale, 0.0f );
}

// One eye of the headset as a render view: the tracked eye pose placed in
// the world, and its off-axis frustum, with fov_x/fov_y the enclosing field
// of view for anything that only estimates.
ID_INLINE void VR_BuildEyeView( const vrFrameState_t &frame, int eye, const idVec3 &eyeOrigin, float trackingYaw, renderView_t &view ) {
	const vrEyeView_t &eyeView = frame.eyes[eye];
	vrPose_t pose = eyeView.pose;
	pose.origin += VR_HeadOffsetCorrection( frame );
	VR_PoseToWorld( pose, eyeOrigin, trackingYaw, view.vieworg, view.viewaxis );
	view.asymmetricFov = true;
	view.fovTanLeft = eyeView.tanLeft;
	view.fovTanRight = eyeView.tanRight;
	view.fovTanUp = eyeView.tanUp;
	view.fovTanDown = eyeView.tanDown;
	const float halfX = Max( idMath::Fabs( eyeView.tanLeft ), idMath::Fabs( eyeView.tanRight ) );
	const float halfY = Max( idMath::Fabs( eyeView.tanUp ), idMath::Fabs( eyeView.tanDown ) );
	view.fov_x = RAD2DEG( 2.0f * idMath::ATan( halfX ) );
	view.fov_y = RAD2DEG( 2.0f * idMath::ATan( halfY ) );
}

// The weapon hand's pointing pose in the world, with the view-weapon offsets
// and pitch applied, for drawing the view weapon at the hand.
ID_INLINE bool VR_WeaponTransform( const vrFrameState_t &frame, const idVec3 &eyeOrigin, float trackingYaw, idVec3 &origin, idMat3 &axis ) {
	const int hand = frame.weaponHand == VR_HAND_LEFT ? VR_HAND_LEFT : VR_HAND_RIGHT;
	const vrPose_t &aim = frame.aim[hand];
	if ( !aim.valid ) {
		return false;
	}
	idVec3 aimOrigin;
	idMat3 aimAxis;
	vrPose_t pose = aim;
	pose.origin += VR_HeadOffsetCorrection( frame );
	VR_PoseToWorld( pose, eyeOrigin, trackingYaw, aimOrigin, aimAxis );
	axis = idAngles( frame.weaponPitch, 0.0f, 0.0f ).ToMat3() * aimAxis;
	origin = aimOrigin + frame.weaponOffset * axis;
	return true;
}

#endif /* !__VRSYSTEM_H__ */

// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
//

/*
===============================================================================

	OpenXR virtual reality.

	One OpenXR session drives presentation, tracking and controller input:

	- The session binds to the renderer's OpenGL context
	  (idRenderSystem::GetVRGraphicsBinding). It opens after the renderer
	  reports a live device and closes before the device is destroyed, so a
	  vid_restart or renderer shutdown never pulls a context out from under
	  the runtime.
	- BeginFrame/EndFrame bracket every presented screen update. xrWaitFrame
	  paces the main loop; the eye and virtual-screen swapchain images are
	  acquired before the renderer's frame and released after it, and the
	  layers submitted to xrEndFrame describe exactly what the renderer drew
	  (GetVRFrameResult) with the poses it drew it from.
	- Controllers reach the engine the way a gamepad does: buttons become the
	  SDL gamepad JOY keys (so default.cfg binds and menu navigation apply),
	  sticks become locomotion and turning, and the aim pose becomes the
	  usercmd angles, which keeps multiplayer authoritative and unchanged.

	See docs/dev/plans/2026-10-02-openxr-vr.md.

===============================================================================
*/

#include "../../idlib/precompiled.h"
#pragma hdrstop

#include "../../framework/VRSystemLocal.h"
#include "../../framework/VRMathCore.h"
#include "../../ui/RetainedUI.h"

#if defined( _WIN32 )
#include <windows.h>
#include <unknwn.h>		// openxr_platform.h's Win32 section names IUnknown
#define XR_USE_PLATFORM_WIN32
#endif
#define XR_USE_GRAPHICS_API_OPENGL
#include <openxr/openxr.h>
#include <openxr/openxr_platform.h>

// The Xlib OpenGL binding, declared without X11 or GLX headers. The layout is
// XrGraphicsBindingOpenGLXlibKHR's: Display *, VisualID (uint32_t),
// GLXFBConfig and GLXContext pointers and a GLXDrawable XID.
typedef struct vrXlibGraphicsBinding_s {
	XrStructureType			type;
	const void *			next;
	void *					xDisplay;
	uint32_t				visualid;
	void *					glxFBConfig;
	unsigned long			glxDrawable;
	void *					glxContext;
} vrXlibGraphicsBinding_t;

#ifndef GL_SRGB8_ALPHA8
#define GL_SRGB8_ALPHA8		0x8C43
#endif
#ifndef GL_RGBA8
#define GL_RGBA8			0x8058
#endif

static const int VR_SCREEN_WIDTH = 1920;
static const int VR_SCREEN_HEIGHT = 1080;
static const int VR_SYSTEM_RETRY_MSEC = 3000;
static const int VR_INPUT_CRITICAL_SECTION = CRITICAL_SECTION_TWO;

enum vrActionId_t {
	VR_ACTION_AIM_POSE,
	VR_ACTION_GRIP_POSE,
	VR_ACTION_TRIGGER,
	VR_ACTION_SQUEEZE,
	VR_ACTION_THUMBSTICK,
	VR_ACTION_THUMBSTICK_CLICK,
	VR_ACTION_PRIMARY,
	VR_ACTION_SECONDARY,
	VR_ACTION_MENU,
	VR_ACTION_HAPTIC,
	VR_ACTION_COUNT
};

static const char *const vrActionNames[VR_ACTION_COUNT] = {
	"aim_pose", "grip_pose", "trigger", "squeeze", "thumbstick",
	"thumbstick_click", "primary", "secondary", "menu", "haptic"
};

// localized action names are shown by runtime binding editors
static const char *const vrActionLocalizedNames[VR_ACTION_COUNT] = {
	"#str_230100", "#str_230101", "#str_230102", "#str_230103", "#str_230104",
	"#str_230105", "#str_230106", "#str_230107", "#str_230108", "#str_230109"
};

static const XrActionType vrActionTypes[VR_ACTION_COUNT] = {
	XR_ACTION_TYPE_POSE_INPUT, XR_ACTION_TYPE_POSE_INPUT, XR_ACTION_TYPE_FLOAT_INPUT,
	XR_ACTION_TYPE_FLOAT_INPUT, XR_ACTION_TYPE_VECTOR2F_INPUT, XR_ACTION_TYPE_BOOLEAN_INPUT,
	XR_ACTION_TYPE_BOOLEAN_INPUT, XR_ACTION_TYPE_BOOLEAN_INPUT, XR_ACTION_TYPE_BOOLEAN_INPUT,
	XR_ACTION_TYPE_VIBRATION_OUTPUT
};

// One suggested binding: an action and the path under /user/hand/<hand>.
typedef struct vrBinding_s {
	int						action;
	int						hand;		// VR_HAND_LEFT / VR_HAND_RIGHT
	const char *			component;
} vrBinding_t;

typedef struct vrProfile_s {
	const char *			path;
	const vrBinding_t *		bindings;
	int						numBindings;
} vrProfile_t;

#define VR_BOTH_HANDS( action, component ) { action, VR_HAND_LEFT, component }, { action, VR_HAND_RIGHT, component }

static const vrBinding_t vrTouchBindings[] = {
	VR_BOTH_HANDS( VR_ACTION_AIM_POSE, "input/aim/pose" ),
	VR_BOTH_HANDS( VR_ACTION_GRIP_POSE, "input/grip/pose" ),
	VR_BOTH_HANDS( VR_ACTION_TRIGGER, "input/trigger/value" ),
	VR_BOTH_HANDS( VR_ACTION_SQUEEZE, "input/squeeze/value" ),
	VR_BOTH_HANDS( VR_ACTION_THUMBSTICK, "input/thumbstick" ),
	VR_BOTH_HANDS( VR_ACTION_THUMBSTICK_CLICK, "input/thumbstick/click" ),
	{ VR_ACTION_PRIMARY, VR_HAND_LEFT, "input/x/click" },
	{ VR_ACTION_PRIMARY, VR_HAND_RIGHT, "input/a/click" },
	{ VR_ACTION_SECONDARY, VR_HAND_LEFT, "input/y/click" },
	{ VR_ACTION_SECONDARY, VR_HAND_RIGHT, "input/b/click" },
	{ VR_ACTION_MENU, VR_HAND_LEFT, "input/menu/click" },
	VR_BOTH_HANDS( VR_ACTION_HAPTIC, "output/haptic" ),
};

// Index has no menu button outside the reserved system button, so the left
// B button opens the menu.
static const vrBinding_t vrIndexBindings[] = {
	VR_BOTH_HANDS( VR_ACTION_AIM_POSE, "input/aim/pose" ),
	VR_BOTH_HANDS( VR_ACTION_GRIP_POSE, "input/grip/pose" ),
	VR_BOTH_HANDS( VR_ACTION_TRIGGER, "input/trigger/value" ),
	VR_BOTH_HANDS( VR_ACTION_SQUEEZE, "input/squeeze/value" ),
	VR_BOTH_HANDS( VR_ACTION_THUMBSTICK, "input/thumbstick" ),
	VR_BOTH_HANDS( VR_ACTION_THUMBSTICK_CLICK, "input/thumbstick/click" ),
	VR_BOTH_HANDS( VR_ACTION_PRIMARY, "input/a/click" ),
	{ VR_ACTION_SECONDARY, VR_HAND_RIGHT, "input/b/click" },
	{ VR_ACTION_MENU, VR_HAND_LEFT, "input/b/click" },
	VR_BOTH_HANDS( VR_ACTION_HAPTIC, "output/haptic" ),
};

static const vrBinding_t vrViveBindings[] = {
	VR_BOTH_HANDS( VR_ACTION_AIM_POSE, "input/aim/pose" ),
	VR_BOTH_HANDS( VR_ACTION_GRIP_POSE, "input/grip/pose" ),
	VR_BOTH_HANDS( VR_ACTION_TRIGGER, "input/trigger/value" ),
	VR_BOTH_HANDS( VR_ACTION_SQUEEZE, "input/squeeze/click" ),
	VR_BOTH_HANDS( VR_ACTION_THUMBSTICK, "input/trackpad" ),
	VR_BOTH_HANDS( VR_ACTION_THUMBSTICK_CLICK, "input/trackpad/click" ),
	{ VR_ACTION_MENU, VR_HAND_LEFT, "input/menu/click" },
	{ VR_ACTION_SECONDARY, VR_HAND_RIGHT, "input/menu/click" },
	VR_BOTH_HANDS( VR_ACTION_HAPTIC, "output/haptic" ),
};

static const vrBinding_t vrMotionControllerBindings[] = {
	VR_BOTH_HANDS( VR_ACTION_AIM_POSE, "input/aim/pose" ),
	VR_BOTH_HANDS( VR_ACTION_GRIP_POSE, "input/grip/pose" ),
	VR_BOTH_HANDS( VR_ACTION_TRIGGER, "input/trigger/value" ),
	VR_BOTH_HANDS( VR_ACTION_SQUEEZE, "input/squeeze/click" ),
	VR_BOTH_HANDS( VR_ACTION_THUMBSTICK, "input/thumbstick" ),
	VR_BOTH_HANDS( VR_ACTION_THUMBSTICK_CLICK, "input/thumbstick/click" ),
	VR_BOTH_HANDS( VR_ACTION_PRIMARY, "input/trackpad/click" ),
	{ VR_ACTION_MENU, VR_HAND_LEFT, "input/menu/click" },
	{ VR_ACTION_SECONDARY, VR_HAND_RIGHT, "input/menu/click" },
	VR_BOTH_HANDS( VR_ACTION_HAPTIC, "output/haptic" ),
};

static const vrBinding_t vrSimpleBindings[] = {
	VR_BOTH_HANDS( VR_ACTION_AIM_POSE, "input/aim/pose" ),
	VR_BOTH_HANDS( VR_ACTION_GRIP_POSE, "input/grip/pose" ),
	VR_BOTH_HANDS( VR_ACTION_TRIGGER, "input/select/click" ),
	{ VR_ACTION_MENU, VR_HAND_LEFT, "input/menu/click" },
	{ VR_ACTION_SECONDARY, VR_HAND_RIGHT, "input/menu/click" },
	VR_BOTH_HANDS( VR_ACTION_HAPTIC, "output/haptic" ),
};

static const vrProfile_t vrProfiles[] = {
	{ "/interaction_profiles/oculus/touch_controller", vrTouchBindings, sizeof( vrTouchBindings ) / sizeof( vrTouchBindings[0] ) },
	{ "/interaction_profiles/valve/index_controller", vrIndexBindings, sizeof( vrIndexBindings ) / sizeof( vrIndexBindings[0] ) },
	{ "/interaction_profiles/htc/vive_controller", vrViveBindings, sizeof( vrViveBindings ) / sizeof( vrViveBindings[0] ) },
	{ "/interaction_profiles/microsoft/motion_controller", vrMotionControllerBindings, sizeof( vrMotionControllerBindings ) / sizeof( vrMotionControllerBindings[0] ) },
	{ "/interaction_profiles/khr/simple_controller", vrSimpleBindings, sizeof( vrSimpleBindings ) / sizeof( vrSimpleBindings[0] ) },
};

/*
===============================================================================

	idVRSystemOpenXR

===============================================================================
*/

class idVRSystemOpenXR : public idVRSystem {
public:
							idVRSystemOpenXR( void );

	virtual void			Init( void );
	virtual void			Shutdown( void );
	virtual void			RendererStarted( void );
	virtual void			RendererStopping( void );
	virtual void			BeginFrame( void );
	virtual void			EndFrame( void );
	virtual bool			IsPacing( void ) const;
	virtual bool			IsActive( void ) const;
	virtual void			GetFrameState( vrFrameState_t &state ) const;
	virtual bool			GetUsercmdInput( float otherYawDelta, float currentYaw, vrUsercmdInput_t &input );
	virtual void			DrawMenuPointer( void );
	virtual void			Vibrate( int hand, float amplitude, int durationMsec );
	virtual void			ShiftTrackingOrigin( const idVec3 &trackingDelta );

	void					RequestRestart( void ) { restartRequested = true; }
	void					RequestRecenter( void ) { recenterRequested = true; }
	void					PrintStatus( void ) const;

private:
	struct swapchain_t {
		XrSwapchain			handle;
		int					width;
		int					height;
		idList<uint32_t>	images;
		uint32_t			acquiredIndex;
		bool				acquired;
	};

	struct handInput_t {
		float				trigger;
		float				squeeze;
		float				stickX, stickY;
		bool				stickClick;
		bool				primary;
		bool				secondary;
		bool				menu;
	};

	// lifecycle
	bool					Check( XrResult result, const char *what );
	bool					CreateInstance( void );
	void					DestroyInstance( void );
	bool					AcquireSystem( void );
	bool					CreateSession( void );
	void					DestroySession( void );
	bool					CreateSwapchain( swapchain_t &swapchain, int width, int height );
	void					DestroySwapchain( swapchain_t &swapchain );
	bool					CreateActions( void );
	void					DestroyActions( void );
	XrPath					Path( const char *text );
	void					StartIfRequested( void );
	void					PollEvents( void );
	void					HandleSessionState( XrSessionState state );

	// per frame
	void					LocateFrame( XrTime time );
	void					SyncInput( float frameSeconds );
	void					PostKey( int key, bool down );
	void					UpdateKey( int slot, int key, bool down );
	bool					MenuMode( void ) const;
	bool					OffHandOnForegrip( int weaponHand ) const;
	void					ApplyTwoHandedAim( int weaponHand );
	void					UpdateMenuPointer( int weaponHand, bool menu );
	void					AnchorScreen( void );
	void					ScreenQuadSize( float &width, float &height ) const;
	void					ScreenSizeForWindow( int &width, int &height ) const;
	bool					ResizeScreenSwapchain( void );
	bool					AcquireImages( void );
	void					ReleaseImages( void );
	vrPose_t				ToEnginePose( const XrPosef &pose, bool valid ) const;
	XrPosef					RecenteredLocalPose( const XrPosef &pose ) const;

	// instance and session
	XrInstance				instance;
	XrSystemId				systemId;
	XrSession				session;
	XrSessionState			sessionState;
	XrSpace					localSpace;
	XrSpace					viewSpace;
	XrEnvironmentBlendMode	blendMode;
	PFN_xrGetOpenGLGraphicsRequirementsKHR getGLRequirements;
	bool					sessionRunning;
	bool					sessionFocused;
	bool					rendererReady;
	bool					restartRequested;
	bool					recenterRequested;
	bool					systemUnavailableLogged;
	bool					startFailureLogged;	// "no runtime" style warnings print once per start
	bool					runtimeStopped;		// the runtime ended VR: wait for vr_restart
	int						nextSystemRetryTime;
	idStr					runtimeName;
	idStr					systemName;
	idStr					interactionProfile;

	swapchain_t				eyeSwapchains[VR_NUM_EYES];
	swapchain_t				screenSwapchain;
	int64_t					swapchainFormat;
	int						recommendedEyeWidth;
	int						recommendedEyeHeight;

	// actions
	XrActionSet				actionSet;
	XrAction				actions[VR_ACTION_COUNT];
	XrPath					handPaths[VR_NUM_HANDS];
	XrSpace					aimSpaces[VR_NUM_HANDS];
	XrSpace					gripSpaces[VR_NUM_HANDS];
	bool					actionsAttached;

	// frame
	bool					frameOpen;
	bool					frameShouldRender;
	XrTime					frameDisplayTime;
	XrView					views[VR_NUM_EYES];
	bool					viewsValid;
	int						lastFrameMsec;
	vrFrameState_t			frame;
	XrPosef					recenterPose;		// tracking origin in the runtime's LOCAL space (yaw only)
	XrPosef					screenAnchor;		// virtual screen centre in LOCAL space
	bool					screenAnchored;
	bool					lastFrameHud;
	int						screenResizeFailedWidth;
	int						screenResizeFailedHeight;
	XrPosef					aimLocalPoses[VR_NUM_HANDS];	// raw LOCAL space, for the menu pointer
	bool					aimLocalValid[VR_NUM_HANDS];
	bool					pointerOnScreen;	// a menu took the pointer at ( pointerU, pointerV )
	float					pointerU;
	float					pointerV;
	const idMaterial *		pointerMaterial;

	// input (shared with the async usercmd thread under VR_INPUT_CRITICAL_SECTION)
	handInput_t				hands[VR_NUM_HANDS];
	bool					inputValid;
	bool					bodyYawValid;
	float					bodyYaw;
	float					aimLocalYaw;
	float					aimLocalPitch;
	float					moveForward;
	float					moveRight;
	vrSnapTurnState_t		snapTurn;
	int						heldKeys[16];
	bool					twoHanded;		// the off hand holds the gun's foregrip (vr_twoHanded)
};

static idVRSystemOpenXR *	vrOpenXR = NULL;

idVRSystem *VR_GetOpenXRSystem( void ) {
	static idVRSystemOpenXR system;
	vrOpenXR = &system;
	return &system;
}

static XrPosef VR_IdentityPose( void ) {
	XrPosef pose;
	pose.orientation.x = pose.orientation.y = pose.orientation.z = 0.0f;
	pose.orientation.w = 1.0f;
	pose.position.x = pose.position.y = pose.position.z = 0.0f;
	return pose;
}

static vrQuat_t VR_FromXrQuat( const XrQuaternionf &q ) {
	vrQuat_t r = { q.x, q.y, q.z, q.w };
	return r;
}

static XrQuaternionf VR_ToXrQuat( const vrQuat_t &q ) {
	XrQuaternionf r;
	r.x = q.x;
	r.y = q.y;
	r.z = q.z;
	r.w = q.w;
	return r;
}

static vrVec3_t VR_FromXrVec( const XrVector3f &v ) {
	return VR_Vec3( v.x, v.y, v.z );
}

static XrVector3f VR_ToXrVec( const vrVec3_t &v ) {
	XrVector3f r;
	r.x = v.x;
	r.y = v.y;
	r.z = v.z;
	return r;
}

// a * b: b expressed in a's frame
static XrPosef VR_PoseMultiply( const XrPosef &a, const XrPosef &b ) {
	const vrQuat_t qa = VR_FromXrQuat( a.orientation );
	XrPosef r;
	r.orientation = VR_ToXrQuat( VR_QuatNormalize( VR_QuatMultiply( qa, VR_FromXrQuat( b.orientation ) ) ) );
	r.position = VR_ToXrVec( VR_Add( VR_FromXrVec( a.position ), VR_RotateVector( qa, VR_FromXrVec( b.position ) ) ) );
	return r;
}

static XrPosef VR_PoseInverse( const XrPosef &a ) {
	const vrQuat_t inverse = VR_QuatConjugate( VR_QuatNormalize( VR_FromXrQuat( a.orientation ) ) );
	XrPosef r;
	r.orientation = VR_ToXrQuat( inverse );
	r.position = VR_ToXrVec( VR_Scale( VR_RotateVector( inverse, VR_FromXrVec( a.position ) ), -1.0f ) );
	return r;
}

// The heading of an OpenXR orientation as a rotation about +Y only.
static XrQuaternionf VR_YawOnly( const XrQuaternionf &orientation ) {
	const vrVec3_t forward = VR_RotateVector( VR_QuatNormalize( VR_FromXrQuat( orientation ) ), VR_Vec3( 0.0f, 0.0f, -1.0f ) );
	const float yaw = std::atan2( -forward.x, -forward.z );
	XrQuaternionf q;
	q.x = 0.0f;
	q.y = std::sin( yaw * 0.5f );
	q.z = 0.0f;
	q.w = std::cos( yaw * 0.5f );
	return q;
}

idVRSystemOpenXR::idVRSystemOpenXR( void ) {
	instance = XR_NULL_HANDLE;
	systemId = XR_NULL_SYSTEM_ID;
	session = XR_NULL_HANDLE;
	sessionState = XR_SESSION_STATE_UNKNOWN;
	localSpace = XR_NULL_HANDLE;
	viewSpace = XR_NULL_HANDLE;
	blendMode = XR_ENVIRONMENT_BLEND_MODE_OPAQUE;
	getGLRequirements = NULL;
	sessionRunning = false;
	sessionFocused = false;
	rendererReady = false;
	restartRequested = false;
	recenterRequested = true;
	systemUnavailableLogged = false;
	startFailureLogged = false;
	runtimeStopped = false;
	nextSystemRetryTime = 0;
	swapchain_t *chains[3] = { &eyeSwapchains[0], &eyeSwapchains[1], &screenSwapchain };
	for ( int i = 0; i < 3; i++ ) {
		chains[i]->handle = XR_NULL_HANDLE;
		chains[i]->width = chains[i]->height = 0;
		chains[i]->acquiredIndex = 0;
		chains[i]->acquired = false;
	}
	swapchainFormat = 0;
	recommendedEyeWidth = recommendedEyeHeight = 0;
	actionSet = XR_NULL_HANDLE;
	for ( int i = 0; i < VR_ACTION_COUNT; i++ ) {
		actions[i] = XR_NULL_HANDLE;
	}
	for ( int i = 0; i < VR_NUM_HANDS; i++ ) {
		handPaths[i] = XR_NULL_PATH;
		aimSpaces[i] = XR_NULL_HANDLE;
		gripSpaces[i] = XR_NULL_HANDLE;
	}
	actionsAttached = false;
	frameOpen = false;
	frameShouldRender = false;
	frameDisplayTime = 0;
	memset( views, 0, sizeof( views ) );
	viewsValid = false;
	lastFrameMsec = 0;
	memset( &frame, 0, sizeof( frame ) );
	recenterPose = VR_IdentityPose();
	screenAnchor = VR_IdentityPose();
	screenAnchored = false;
	lastFrameHud = false;
	screenResizeFailedWidth = screenResizeFailedHeight = 0;
	for ( int i = 0; i < VR_NUM_HANDS; i++ ) {
		aimLocalPoses[i] = VR_IdentityPose();
		aimLocalValid[i] = false;
	}
	pointerOnScreen = false;
	pointerU = pointerV = 0.0f;
	pointerMaterial = NULL;
	memset( hands, 0, sizeof( hands ) );
	inputValid = false;
	bodyYawValid = false;
	bodyYaw = 0.0f;
	aimLocalYaw = aimLocalPitch = 0.0f;
	moveForward = moveRight = 0.0f;
	snapTurn.latched = false;
	memset( heldKeys, 0, sizeof( heldKeys ) );
	twoHanded = false;
}

/*
====================
Commands
====================
*/
static void VR_Restart_f( const idCmdArgs &args ) {
	(void)args;
	if ( vrOpenXR != NULL ) {
		vrOpenXR->RequestRestart();
	}
}

static void VR_Recenter_f( const idCmdArgs &args ) {
	(void)args;
	if ( vrOpenXR != NULL ) {
		vrOpenXR->RequestRecenter();
	}
}

static void VR_Status_f( const idCmdArgs &args ) {
	(void)args;
	if ( vrOpenXR != NULL ) {
		vrOpenXR->PrintStatus();
	}
}

void idVRSystemOpenXR::Init( void ) {
	cmdSystem->AddCommand( "vr_restart", VR_Restart_f, CMD_FL_SYSTEM, "restarts the OpenXR session, applying vr_enable and vr_renderScale" );
	cmdSystem->AddCommand( "vr_recenter", VR_Recenter_f, CMD_FL_SYSTEM, "makes the current head position and heading the VR origin" );
	cmdSystem->AddCommand( "vr_status", VR_Status_f, CMD_FL_SYSTEM, "prints the OpenXR runtime, session and tracking state" );
	vr_enable.ClearModified();
}

void idVRSystemOpenXR::Shutdown( void ) {
	DestroySession();
	DestroyInstance();
	cmdSystem->RemoveCommand( "vr_restart" );
	cmdSystem->RemoveCommand( "vr_recenter" );
	cmdSystem->RemoveCommand( "vr_status" );
}

void idVRSystemOpenXR::RendererStarted( void ) {
	rendererReady = true;
}

void idVRSystemOpenXR::RendererStopping( void ) {
	// the swapchain images live in this context's share group
	DestroySession();
	rendererReady = false;
}

bool idVRSystemOpenXR::IsPacing( void ) const {
	return sessionRunning;
}

bool idVRSystemOpenXR::IsActive( void ) const {
	return sessionRunning && frame.active;
}

void idVRSystemOpenXR::PrintStatus( void ) const {
	common->Printf( "OpenXR: %s\n", instance != XR_NULL_HANDLE ? "instance created" : "no instance" );
	if ( runtimeStopped ) {
		common->Printf( "  the runtime ended VR; vr_restart starts it again\n" );
	}
	if ( instance != XR_NULL_HANDLE ) {
		common->Printf( "  runtime: %s\n", runtimeName.c_str() );
		common->Printf( "  system: %s\n", systemId != XR_NULL_SYSTEM_ID ? systemName.c_str() : "<no headset>" );
	}
	common->Printf( "  session: %s, state %d, %s\n", session != XR_NULL_HANDLE ? "created" : "none",
		static_cast<int>( sessionState ), sessionRunning ? ( sessionFocused ? "running, focused" : "running" ) : "not running" );
	if ( session != XR_NULL_HANDLE ) {
		common->Printf( "  eyes: %dx%d (recommended %dx%d), virtual screen %dx%d, format 0x%llx\n",
			eyeSwapchains[0].width, eyeSwapchains[0].height, recommendedEyeWidth, recommendedEyeHeight,
			screenSwapchain.width, screenSwapchain.height, static_cast<unsigned long long>( swapchainFormat ) );
		common->Printf( "  interaction profile: %s\n", interactionProfile.Length() ? interactionProfile.c_str() : "<none>" );
		common->Printf( "  frame %d, head %s ( %.1f %.1f %.1f ), body yaw %.2f%s\n", frame.frameNumber, frame.head.valid ? "tracked" : "lost",
			frame.head.origin.x, frame.head.origin.y, frame.head.origin.z, bodyYaw, bodyYawValid ? "" : " (not yet driving input)" );
	}
}

/*
====================
idVRSystemOpenXR::Check

Logs a failure. Losing the instance or the session tears down what depends
on it; the next frame starts over if VR is still enabled.
====================
*/
bool idVRSystemOpenXR::Check( XrResult result, const char *what ) {
	if ( XR_SUCCEEDED( result ) ) {
		return true;
	}
	char name[XR_MAX_RESULT_STRING_SIZE];
	name[0] = '\0';
	if ( instance == XR_NULL_HANDLE || xrResultToString( instance, result, name ) != XR_SUCCESS ) {
		idStr::snPrintf( name, sizeof( name ), "%d", static_cast<int>( result ) );
	}
	common->Warning( "OpenXR: %s failed: %s", what, name );
	if ( result == XR_ERROR_SESSION_LOST ) {
		DestroySession();
	} else if ( result == XR_ERROR_INSTANCE_LOST || result == XR_ERROR_RUNTIME_FAILURE ) {
		DestroySession();
		DestroyInstance();
		runtimeStopped = true;
	}
	return false;
}

XrPath idVRSystemOpenXR::Path( const char *text ) {
	XrPath path = XR_NULL_PATH;
	if ( xrStringToPath( instance, text, &path ) != XR_SUCCESS ) {
		return XR_NULL_PATH;
	}
	return path;
}

/*
====================
idVRSystemOpenXR::CreateInstance
====================
*/
bool idVRSystemOpenXR::CreateInstance( void ) {
	uint32_t extensionCount = 0;
	XrResult result = xrEnumerateInstanceExtensionProperties( NULL, 0, &extensionCount, NULL );
	if ( XR_FAILED( result ) ) {
		if ( !startFailureLogged ) {
			common->Warning( "OpenXR: no runtime is available (%d); install and activate one (SteamVR, Meta Quest Link, Monado...)", static_cast<int>( result ) );
			startFailureLogged = true;
		}
		return false;
	}
	idList<XrExtensionProperties> extensions;
	extensions.SetNum( static_cast<int>( extensionCount ) );
	for ( int i = 0; i < extensions.Num(); i++ ) {
		extensions[i].type = XR_TYPE_EXTENSION_PROPERTIES;
		extensions[i].next = NULL;
	}
	result = xrEnumerateInstanceExtensionProperties( NULL, extensionCount, &extensionCount, extensions.Ptr() );
	bool haveOpenGL = false;
	for ( int i = 0; XR_SUCCEEDED( result ) && i < extensions.Num(); i++ ) {
		if ( idStr::Cmp( extensions[i].extensionName, XR_KHR_OPENGL_ENABLE_EXTENSION_NAME ) == 0 ) {
			haveOpenGL = true;
		}
	}
	if ( !haveOpenGL ) {
		if ( !startFailureLogged ) {
			common->Warning( "OpenXR: the active runtime does not support OpenGL (%s); VR stays off", XR_KHR_OPENGL_ENABLE_EXTENSION_NAME );
			startFailureLogged = true;
		}
		return false;
	}

	const char *enabledExtensions[] = { XR_KHR_OPENGL_ENABLE_EXTENSION_NAME };
	XrInstanceCreateInfo createInfo;
	memset( &createInfo, 0, sizeof( createInfo ) );
	createInfo.type = XR_TYPE_INSTANCE_CREATE_INFO;
	idStr::Copynz( createInfo.applicationInfo.applicationName, "openQ4", sizeof( createInfo.applicationInfo.applicationName ) );
	createInfo.applicationInfo.applicationVersion = 1;
	idStr::Copynz( createInfo.applicationInfo.engineName, "openQ4", sizeof( createInfo.applicationInfo.engineName ) );
	createInfo.applicationInfo.engineVersion = 1;
	createInfo.applicationInfo.apiVersion = XR_API_VERSION_1_0;
	createInfo.enabledExtensionCount = 1;
	createInfo.enabledExtensionNames = enabledExtensions;
	if ( !Check( xrCreateInstance( &createInfo, &instance ), "xrCreateInstance" ) ) {
		instance = XR_NULL_HANDLE;
		return false;
	}

	XrInstanceProperties properties;
	memset( &properties, 0, sizeof( properties ) );
	properties.type = XR_TYPE_INSTANCE_PROPERTIES;
	if ( xrGetInstanceProperties( instance, &properties ) == XR_SUCCESS ) {
		runtimeName = va( "%s %u.%u.%u", properties.runtimeName,
			static_cast<unsigned>( XR_VERSION_MAJOR( properties.runtimeVersion ) ),
			static_cast<unsigned>( XR_VERSION_MINOR( properties.runtimeVersion ) ),
			static_cast<unsigned>( XR_VERSION_PATCH( properties.runtimeVersion ) ) );
	} else {
		runtimeName = "unknown";
	}

	PFN_xrVoidFunction function = NULL;
	if ( !Check( xrGetInstanceProcAddr( instance, "xrGetOpenGLGraphicsRequirementsKHR", &function ), "xrGetInstanceProcAddr( xrGetOpenGLGraphicsRequirementsKHR )" ) ) {
		DestroyInstance();
		return false;
	}
	getGLRequirements = reinterpret_cast<PFN_xrGetOpenGLGraphicsRequirementsKHR>( function );
	common->Printf( "OpenXR: runtime %s\n", runtimeName.c_str() );
	systemUnavailableLogged = false;
	nextSystemRetryTime = 0;
	return true;
}

void idVRSystemOpenXR::DestroyInstance( void ) {
	DestroySession();
	if ( instance != XR_NULL_HANDLE ) {
		xrDestroyInstance( instance );
		instance = XR_NULL_HANDLE;
	}
	systemId = XR_NULL_SYSTEM_ID;
	getGLRequirements = NULL;
	for ( int i = 0; i < VR_NUM_HANDS; i++ ) {
		handPaths[i] = XR_NULL_PATH;
	}
}

/*
====================
idVRSystemOpenXR::AcquireSystem

A headset that is switched off or unplugged is not an error: the system is
asked for again every few seconds while VR stays enabled.
====================
*/
bool idVRSystemOpenXR::AcquireSystem( void ) {
	if ( systemId != XR_NULL_SYSTEM_ID ) {
		return true;
	}
	if ( Sys_Milliseconds() < nextSystemRetryTime ) {
		return false;
	}
	XrSystemGetInfo getInfo;
	memset( &getInfo, 0, sizeof( getInfo ) );
	getInfo.type = XR_TYPE_SYSTEM_GET_INFO;
	getInfo.formFactor = XR_FORM_FACTOR_HEAD_MOUNTED_DISPLAY;
	const XrResult result = xrGetSystem( instance, &getInfo, &systemId );
	if ( result == XR_ERROR_FORM_FACTOR_UNAVAILABLE ) {
		systemId = XR_NULL_SYSTEM_ID;
		nextSystemRetryTime = Sys_Milliseconds() + VR_SYSTEM_RETRY_MSEC;
		if ( !systemUnavailableLogged ) {
			common->Printf( "OpenXR: no headset is connected yet; waiting for one\n" );
			systemUnavailableLogged = true;
		}
		return false;
	}
	if ( !Check( result, "xrGetSystem" ) ) {
		systemId = XR_NULL_SYSTEM_ID;
		nextSystemRetryTime = Sys_Milliseconds() + VR_SYSTEM_RETRY_MSEC;
		return false;
	}

	XrSystemProperties properties;
	memset( &properties, 0, sizeof( properties ) );
	properties.type = XR_TYPE_SYSTEM_PROPERTIES;
	if ( xrGetSystemProperties( instance, systemId, &properties ) == XR_SUCCESS ) {
		systemName = properties.systemName;
	}
	common->Printf( "OpenXR: headset %s\n", systemName.c_str() );
	return true;
}

/*
====================
idVRSystemOpenXR::CreateSession
====================
*/
bool idVRSystemOpenXR::CreateSession( void ) {
	renderVRGraphicsBinding_t binding;
	if ( !renderSystem->GetVRGraphicsBinding( binding ) ) {
		static bool warned = false;
		if ( !warned ) {
			common->Warning( "OpenXR: VR needs the OpenGL renderer (r_renderApi gl)%s; VR stays off",
#if defined( __linux__ )
				" on an X11 or XWayland GLX context (on Wayland, start with OPENQ4_FORCE_X11=1)"
#else
				""
#endif
				);
			warned = true;
		}
		return false;
	}

	XrGraphicsRequirementsOpenGLKHR requirements;
	memset( &requirements, 0, sizeof( requirements ) );
	requirements.type = XR_TYPE_GRAPHICS_REQUIREMENTS_OPENGL_KHR;
	if ( getGLRequirements == NULL || !Check( getGLRequirements( instance, systemId, &requirements ), "xrGetOpenGLGraphicsRequirementsKHR" ) ) {
		return false;
	}
	const XrVersion contextVersion = XR_MAKE_VERSION( binding.glMajor, binding.glMinor, 0 );
	if ( contextVersion < requirements.minApiVersionSupported ) {
		common->Warning( "OpenXR: the runtime needs OpenGL %u.%u, the renderer's context is %d.%d; VR stays off",
			static_cast<unsigned>( XR_VERSION_MAJOR( requirements.minApiVersionSupported ) ),
			static_cast<unsigned>( XR_VERSION_MINOR( requirements.minApiVersionSupported ) ),
			binding.glMajor, binding.glMinor );
		return false;
	}

	XrSessionCreateInfo createInfo;
	memset( &createInfo, 0, sizeof( createInfo ) );
	createInfo.type = XR_TYPE_SESSION_CREATE_INFO;
	createInfo.systemId = systemId;
#if defined( _WIN32 )
	XrGraphicsBindingOpenGLWin32KHR win32Binding;
	memset( &win32Binding, 0, sizeof( win32Binding ) );
	win32Binding.type = XR_TYPE_GRAPHICS_BINDING_OPENGL_WIN32_KHR;
	win32Binding.hDC = static_cast<HDC>( binding.wglDC );
	win32Binding.hGLRC = static_cast<HGLRC>( binding.wglContext );
	createInfo.next = &win32Binding;
#else
	vrXlibGraphicsBinding_t xlibBinding;
	memset( &xlibBinding, 0, sizeof( xlibBinding ) );
	xlibBinding.type = XR_TYPE_GRAPHICS_BINDING_OPENGL_XLIB_KHR;
	xlibBinding.xDisplay = binding.glxDisplay;
	xlibBinding.visualid = binding.glxVisualId;
	xlibBinding.glxFBConfig = binding.glxFBConfig;
	xlibBinding.glxDrawable = binding.glxDrawable;
	xlibBinding.glxContext = binding.glxContext;
	createInfo.next = &xlibBinding;
#endif
	if ( !Check( xrCreateSession( instance, &createInfo, &session ), "xrCreateSession" ) ) {
		session = XR_NULL_HANDLE;
		return false;
	}
	sessionState = XR_SESSION_STATE_UNKNOWN;

	// spaces: LOCAL carries tracking, projection and the virtual screen; VIEW the HUD
	XrReferenceSpaceCreateInfo spaceInfo;
	memset( &spaceInfo, 0, sizeof( spaceInfo ) );
	spaceInfo.type = XR_TYPE_REFERENCE_SPACE_CREATE_INFO;
	spaceInfo.poseInReferenceSpace = VR_IdentityPose();
	spaceInfo.referenceSpaceType = XR_REFERENCE_SPACE_TYPE_LOCAL;
	if ( !Check( xrCreateReferenceSpace( session, &spaceInfo, &localSpace ), "xrCreateReferenceSpace( LOCAL )" ) ) {
		DestroySession();
		return false;
	}
	spaceInfo.referenceSpaceType = XR_REFERENCE_SPACE_TYPE_VIEW;
	if ( !Check( xrCreateReferenceSpace( session, &spaceInfo, &viewSpace ), "xrCreateReferenceSpace( VIEW )" ) ) {
		DestroySession();
		return false;
	}

	// views
	uint32_t viewCount = 0;
	if ( !Check( xrEnumerateViewConfigurationViews( instance, systemId, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, 0, &viewCount, NULL ), "xrEnumerateViewConfigurationViews" )
			|| viewCount != VR_NUM_EYES ) {
		common->Warning( "OpenXR: the headset does not offer a two-view stereo configuration" );
		DestroySession();
		return false;
	}
	XrViewConfigurationView configViews[VR_NUM_EYES];
	for ( int i = 0; i < VR_NUM_EYES; i++ ) {
		memset( &configViews[i], 0, sizeof( configViews[i] ) );
		configViews[i].type = XR_TYPE_VIEW_CONFIGURATION_VIEW;
	}
	if ( !Check( xrEnumerateViewConfigurationViews( instance, systemId, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, VR_NUM_EYES, &viewCount, configViews ), "xrEnumerateViewConfigurationViews" ) ) {
		DestroySession();
		return false;
	}
	recommendedEyeWidth = static_cast<int>( configViews[0].recommendedImageRectWidth );
	recommendedEyeHeight = static_cast<int>( configViews[0].recommendedImageRectHeight );
	const float scale = idMath::ClampFloat( 0.5f, 2.0f, vr_renderScale.GetFloat() );
	const int maxWidth = static_cast<int>( Min( configViews[0].maxImageRectWidth, configViews[1].maxImageRectWidth ) );
	const int maxHeight = static_cast<int>( Min( configViews[0].maxImageRectHeight, configViews[1].maxImageRectHeight ) );
	const int eyeWidth = idMath::ClampInt( 64, Max( 64, maxWidth ), static_cast<int>( recommendedEyeWidth * scale + 0.5f ) );
	const int eyeHeight = idMath::ClampInt( 64, Max( 64, maxHeight ), static_cast<int>( recommendedEyeHeight * scale + 0.5f ) );

	// blend mode: an opaque display; anything else blends with the real world
	uint32_t blendCount = 0;
	blendMode = XR_ENVIRONMENT_BLEND_MODE_OPAQUE;
	if ( xrEnumerateEnvironmentBlendModes( instance, systemId, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, 0, &blendCount, NULL ) == XR_SUCCESS && blendCount > 0 ) {
		idList<XrEnvironmentBlendMode> modes;
		modes.SetNum( static_cast<int>( blendCount ) );
		if ( xrEnumerateEnvironmentBlendModes( instance, systemId, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, blendCount, &blendCount, modes.Ptr() ) == XR_SUCCESS ) {
			blendMode = modes[0];
			for ( int i = 0; i < modes.Num(); i++ ) {
				if ( modes[i] == XR_ENVIRONMENT_BLEND_MODE_OPAQUE ) {
					blendMode = modes[i];
				}
			}
		}
	}

	// swapchain format: sRGB so the compositor reads the engine's gamma-encoded pixels as they are
	uint32_t formatCount = 0;
	swapchainFormat = 0;
	if ( Check( xrEnumerateSwapchainFormats( session, 0, &formatCount, NULL ), "xrEnumerateSwapchainFormats" ) && formatCount > 0 ) {
		idList<int64_t> formats;
		formats.SetNum( static_cast<int>( formatCount ) );
		if ( xrEnumerateSwapchainFormats( session, formatCount, &formatCount, formats.Ptr() ) == XR_SUCCESS ) {
			for ( int i = 0; i < formats.Num() && swapchainFormat == 0; i++ ) {
				if ( formats[i] == GL_SRGB8_ALPHA8 ) {
					swapchainFormat = formats[i];
				}
			}
			for ( int i = 0; i < formats.Num() && swapchainFormat == 0; i++ ) {
				if ( formats[i] == GL_RGBA8 ) {
					swapchainFormat = formats[i];
					common->Warning( "OpenXR: the runtime offers no sRGB swapchain format; colours may look washed out" );
				}
			}
		}
	}
	if ( swapchainFormat == 0 ) {
		common->Warning( "OpenXR: the runtime offers no usable 8-bit colour swapchain format" );
		DestroySession();
		return false;
	}

	for ( int i = 0; i < VR_NUM_EYES; i++ ) {
		if ( !CreateSwapchain( eyeSwapchains[i], eyeWidth, eyeHeight ) ) {
			DestroySession();
			return false;
		}
	}
	int screenWidth = VR_SCREEN_WIDTH, screenHeight = VR_SCREEN_HEIGHT;
	ScreenSizeForWindow( screenWidth, screenHeight );
	if ( !CreateSwapchain( screenSwapchain, screenWidth, screenHeight ) ) {
		DestroySession();
		return false;
	}
	screenResizeFailedWidth = screenResizeFailedHeight = 0;

	if ( !CreateActions() ) {
		// tracking and presentation still work without controllers
		common->Warning( "OpenXR: controller input is unavailable" );
	}

	recenterRequested = true;
	screenAnchored = false;
	bodyYawValid = false;
	common->Printf( "OpenXR: session created, eyes %dx%d (recommended %dx%d), virtual screen %dx%d\n",
		eyeWidth, eyeHeight, recommendedEyeWidth, recommendedEyeHeight, screenWidth, screenHeight );
	return true;
}

void idVRSystemOpenXR::DestroySession( void ) {
	if ( frameOpen && session != XR_NULL_HANDLE ) {
		// an unfinished frame is abandoned with the session
		ReleaseImages();
		frameOpen = false;
	}
	if ( rendererReady && renderSystem != NULL ) {
		renderSystem->SetVRFrame( NULL );
	}
	DestroyActions();
	for ( int i = 0; i < VR_NUM_EYES; i++ ) {
		DestroySwapchain( eyeSwapchains[i] );
	}
	DestroySwapchain( screenSwapchain );
	if ( localSpace != XR_NULL_HANDLE ) {
		xrDestroySpace( localSpace );
		localSpace = XR_NULL_HANDLE;
	}
	if ( viewSpace != XR_NULL_HANDLE ) {
		xrDestroySpace( viewSpace );
		viewSpace = XR_NULL_HANDLE;
	}
	if ( session != XR_NULL_HANDLE ) {
		if ( sessionRunning && sessionState == XR_SESSION_STATE_STOPPING ) {
			xrEndSession( session );
		}
		xrDestroySession( session );
		session = XR_NULL_HANDLE;
		common->Printf( "OpenXR: session closed\n" );
	}
	sessionRunning = false;
	sessionFocused = false;
	sessionState = XR_SESSION_STATE_UNKNOWN;
	viewsValid = false;
	interactionProfile.Clear();

	Sys_EnterCriticalSection( VR_INPUT_CRITICAL_SECTION );
	inputValid = false;
	bodyYawValid = false;
	Sys_LeaveCriticalSection( VR_INPUT_CRITICAL_SECTION );
	memset( &frame, 0, sizeof( frame ) );
	for ( int i = 0; i < 16; i++ ) {
		UpdateKey( i, heldKeys[i], false );
	}
	twoHanded = false;
}

bool idVRSystemOpenXR::CreateSwapchain( swapchain_t &swapchain, int width, int height ) {
	XrSwapchainCreateInfo createInfo;
	memset( &createInfo, 0, sizeof( createInfo ) );
	createInfo.type = XR_TYPE_SWAPCHAIN_CREATE_INFO;
	createInfo.usageFlags = XR_SWAPCHAIN_USAGE_COLOR_ATTACHMENT_BIT | XR_SWAPCHAIN_USAGE_TRANSFER_DST_BIT;
	createInfo.format = swapchainFormat;
	createInfo.sampleCount = 1;
	createInfo.width = static_cast<uint32_t>( width );
	createInfo.height = static_cast<uint32_t>( height );
	createInfo.faceCount = 1;
	createInfo.arraySize = 1;
	createInfo.mipCount = 1;
	swapchain.handle = XR_NULL_HANDLE;
	swapchain.acquired = false;
	swapchain.images.Clear();
	if ( !Check( xrCreateSwapchain( session, &createInfo, &swapchain.handle ), "xrCreateSwapchain" ) ) {
		swapchain.handle = XR_NULL_HANDLE;
		return false;
	}
	uint32_t imageCount = 0;
	if ( !Check( xrEnumerateSwapchainImages( swapchain.handle, 0, &imageCount, NULL ), "xrEnumerateSwapchainImages" ) || imageCount == 0 ) {
		DestroySwapchain( swapchain );
		return false;
	}
	idList<XrSwapchainImageOpenGLKHR> images;
	images.SetNum( static_cast<int>( imageCount ) );
	for ( int i = 0; i < images.Num(); i++ ) {
		images[i].type = XR_TYPE_SWAPCHAIN_IMAGE_OPENGL_KHR;
		images[i].next = NULL;
		images[i].image = 0;
	}
	if ( !Check( xrEnumerateSwapchainImages( swapchain.handle, imageCount, &imageCount,
			reinterpret_cast<XrSwapchainImageBaseHeader *>( images.Ptr() ) ), "xrEnumerateSwapchainImages" ) ) {
		DestroySwapchain( swapchain );
		return false;
	}
	for ( int i = 0; i < images.Num(); i++ ) {
		swapchain.images.Append( images[i].image );
	}
	swapchain.width = width;
	swapchain.height = height;
	return true;
}

void idVRSystemOpenXR::DestroySwapchain( swapchain_t &swapchain ) {
	if ( swapchain.handle != XR_NULL_HANDLE ) {
		xrDestroySwapchain( swapchain.handle );
	}
	swapchain.handle = XR_NULL_HANDLE;
	swapchain.images.Clear();
	swapchain.acquired = false;
	swapchain.width = swapchain.height = 0;
}

/*
====================
idVRSystemOpenXR::CreateActions
====================
*/
bool idVRSystemOpenXR::CreateActions( void ) {
	handPaths[VR_HAND_LEFT] = Path( "/user/hand/left" );
	handPaths[VR_HAND_RIGHT] = Path( "/user/hand/right" );
	if ( handPaths[VR_HAND_LEFT] == XR_NULL_PATH || handPaths[VR_HAND_RIGHT] == XR_NULL_PATH ) {
		return false;
	}

	const idLangDict *strings = common->GetLanguageDict();
	XrActionSetCreateInfo setInfo;
	memset( &setInfo, 0, sizeof( setInfo ) );
	setInfo.type = XR_TYPE_ACTION_SET_CREATE_INFO;
	idStr::Copynz( setInfo.actionSetName, "gameplay", sizeof( setInfo.actionSetName ) );
	idStr::Copynz( setInfo.localizedActionSetName, strings->GetString( "#str_230110" ), sizeof( setInfo.localizedActionSetName ) );
	if ( !Check( xrCreateActionSet( instance, &setInfo, &actionSet ), "xrCreateActionSet" ) ) {
		actionSet = XR_NULL_HANDLE;
		return false;
	}

	for ( int i = 0; i < VR_ACTION_COUNT; i++ ) {
		XrActionCreateInfo actionInfo;
		memset( &actionInfo, 0, sizeof( actionInfo ) );
		actionInfo.type = XR_TYPE_ACTION_CREATE_INFO;
		actionInfo.actionType = vrActionTypes[i];
		idStr::Copynz( actionInfo.actionName, vrActionNames[i], sizeof( actionInfo.actionName ) );
		idStr::Copynz( actionInfo.localizedActionName, strings->GetString( vrActionLocalizedNames[i] ), sizeof( actionInfo.localizedActionName ) );
		actionInfo.countSubactionPaths = VR_NUM_HANDS;
		actionInfo.subactionPaths = handPaths;
		if ( !Check( xrCreateAction( actionSet, &actionInfo, &actions[i] ), "xrCreateAction" ) ) {
			DestroyActions();
			return false;
		}
	}

	// every profile the runtime knows gets the same layout; a profile it
	// rejects (an extension profile on an older runtime) is simply skipped
	for ( size_t p = 0; p < sizeof( vrProfiles ) / sizeof( vrProfiles[0] ); p++ ) {
		const vrProfile_t &profile = vrProfiles[p];
		idList<XrActionSuggestedBinding> suggested;
		for ( int b = 0; b < profile.numBindings; b++ ) {
			const vrBinding_t &binding = profile.bindings[b];
			XrActionSuggestedBinding entry;
			entry.action = actions[binding.action];
			entry.binding = Path( va( "/user/hand/%s/%s", binding.hand == VR_HAND_LEFT ? "left" : "right", binding.component ) );
			if ( entry.binding != XR_NULL_PATH ) {
				suggested.Append( entry );
			}
		}
		XrInteractionProfileSuggestedBinding suggestion;
		memset( &suggestion, 0, sizeof( suggestion ) );
		suggestion.type = XR_TYPE_INTERACTION_PROFILE_SUGGESTED_BINDING;
		suggestion.interactionProfile = Path( profile.path );
		suggestion.countSuggestedBindings = static_cast<uint32_t>( suggested.Num() );
		suggestion.suggestedBindings = suggested.Ptr();
		const XrResult result = xrSuggestInteractionProfileBindings( instance, &suggestion );
		if ( XR_FAILED( result ) && vr_debug.GetInteger() > 0 ) {
			common->Printf( "OpenXR: runtime declined bindings for %s (%d)\n", profile.path, static_cast<int>( result ) );
		}
	}

	for ( int hand = 0; hand < VR_NUM_HANDS; hand++ ) {
		XrActionSpaceCreateInfo spaceInfo;
		memset( &spaceInfo, 0, sizeof( spaceInfo ) );
		spaceInfo.type = XR_TYPE_ACTION_SPACE_CREATE_INFO;
		spaceInfo.subactionPath = handPaths[hand];
		spaceInfo.poseInActionSpace = VR_IdentityPose();
		spaceInfo.action = actions[VR_ACTION_AIM_POSE];
		if ( !Check( xrCreateActionSpace( session, &spaceInfo, &aimSpaces[hand] ), "xrCreateActionSpace( aim )" ) ) {
			aimSpaces[hand] = XR_NULL_HANDLE;
		}
		spaceInfo.action = actions[VR_ACTION_GRIP_POSE];
		if ( !Check( xrCreateActionSpace( session, &spaceInfo, &gripSpaces[hand] ), "xrCreateActionSpace( grip )" ) ) {
			gripSpaces[hand] = XR_NULL_HANDLE;
		}
	}

	XrSessionActionSetsAttachInfo attachInfo;
	memset( &attachInfo, 0, sizeof( attachInfo ) );
	attachInfo.type = XR_TYPE_SESSION_ACTION_SETS_ATTACH_INFO;
	attachInfo.countActionSets = 1;
	attachInfo.actionSets = &actionSet;
	actionsAttached = Check( xrAttachSessionActionSets( session, &attachInfo ), "xrAttachSessionActionSets" );
	return actionsAttached;
}

void idVRSystemOpenXR::DestroyActions( void ) {
	for ( int hand = 0; hand < VR_NUM_HANDS; hand++ ) {
		if ( aimSpaces[hand] != XR_NULL_HANDLE ) {
			xrDestroySpace( aimSpaces[hand] );
			aimSpaces[hand] = XR_NULL_HANDLE;
		}
		if ( gripSpaces[hand] != XR_NULL_HANDLE ) {
			xrDestroySpace( gripSpaces[hand] );
			gripSpaces[hand] = XR_NULL_HANDLE;
		}
	}
	if ( actionSet != XR_NULL_HANDLE ) {
		// destroying the set destroys its actions
		xrDestroyActionSet( actionSet );
		actionSet = XR_NULL_HANDLE;
	}
	for ( int i = 0; i < VR_ACTION_COUNT; i++ ) {
		actions[i] = XR_NULL_HANDLE;
	}
	actionsAttached = false;
}

/*
====================
idVRSystemOpenXR::StartIfRequested
====================
*/
void idVRSystemOpenXR::StartIfRequested( void ) {
	if ( restartRequested || vr_enable.IsModified() || vr_renderScale.IsModified() ) {
		const bool restart = restartRequested || vr_renderScale.IsModified();
		restartRequested = false;
		vr_enable.ClearModified();
		vr_renderScale.ClearModified();
		if ( !vr_enable.GetBool() || restart ) {
			DestroySession();
			DestroyInstance();
		}
		runtimeStopped = false;
		startFailureLogged = false;
	}
	// Once the runtime has ended VR, creating an instance could relaunch it
	// (SteamVR starts with its first client), so only vr_restart resumes.
	if ( runtimeStopped || !vr_enable.GetBool() || !rendererReady || !renderSystem->IsOpenGLRunning() ) {
		return;
	}
	if ( instance == XR_NULL_HANDLE ) {
		static int nextAttempt = 0;
		if ( Sys_Milliseconds() < nextAttempt ) {
			return;
		}
		if ( !CreateInstance() ) {
			// no runtime: try again later rather than every frame
			nextAttempt = Sys_Milliseconds() + VR_SYSTEM_RETRY_MSEC * 3;
			return;
		}
	}
	if ( !AcquireSystem() ) {
		return;
	}
	if ( session == XR_NULL_HANDLE ) {
		static int nextAttempt = 0;
		if ( Sys_Milliseconds() < nextAttempt ) {
			return;
		}
		if ( !CreateSession() ) {
			nextAttempt = Sys_Milliseconds() + VR_SYSTEM_RETRY_MSEC;
		}
	}
}

/*
====================
idVRSystemOpenXR::PollEvents
====================
*/
void idVRSystemOpenXR::PollEvents( void ) {
	for ( int guard = 0; guard < 64 && instance != XR_NULL_HANDLE; guard++ ) {
		XrEventDataBuffer event;
		memset( &event, 0, sizeof( event ) );
		event.type = XR_TYPE_EVENT_DATA_BUFFER;
		const XrResult result = xrPollEvent( instance, &event );
		if ( result != XR_SUCCESS ) {
			if ( XR_FAILED( result ) ) {
				Check( result, "xrPollEvent" );
			}
			return;
		}
		switch ( event.type ) {
			case XR_TYPE_EVENT_DATA_SESSION_STATE_CHANGED: {
				const XrEventDataSessionStateChanged *changed = reinterpret_cast<const XrEventDataSessionStateChanged *>( &event );
				if ( changed->session == session ) {
					HandleSessionState( changed->state );
				}
				break;
			}
			case XR_TYPE_EVENT_DATA_INSTANCE_LOSS_PENDING:
				common->Warning( "OpenXR: the runtime is going away; vr_restart starts VR again once it is back" );
				DestroySession();
				DestroyInstance();
				runtimeStopped = true;
				return;
			case XR_TYPE_EVENT_DATA_INTERACTION_PROFILE_CHANGED: {
				interactionProfile.Clear();
				XrInteractionProfileState state;
				memset( &state, 0, sizeof( state ) );
				state.type = XR_TYPE_INTERACTION_PROFILE_STATE;
				const XrPath hand = vr_leftHanded.GetBool() ? handPaths[VR_HAND_LEFT] : handPaths[VR_HAND_RIGHT];
				if ( session != XR_NULL_HANDLE && hand != XR_NULL_PATH && xrGetCurrentInteractionProfile( session, hand, &state ) == XR_SUCCESS
						&& state.interactionProfile != XR_NULL_PATH ) {
					char path[XR_MAX_PATH_LENGTH];
					uint32_t length = 0;
					if ( xrPathToString( instance, state.interactionProfile, sizeof( path ), &length, path ) == XR_SUCCESS ) {
						interactionProfile = path;
					}
				}
				common->Printf( "OpenXR: controllers %s\n", interactionProfile.Length() ? interactionProfile.c_str() : "disconnected" );
				break;
			}
			case XR_TYPE_EVENT_DATA_REFERENCE_SPACE_CHANGE_PENDING:
				// the user recentred in the runtime: follow it
				recenterRequested = true;
				break;
			default:
				break;
		}
	}
}

void idVRSystemOpenXR::HandleSessionState( XrSessionState state ) {
	sessionState = state;
	if ( vr_debug.GetInteger() > 0 ) {
		common->Printf( "OpenXR: session state %d\n", static_cast<int>( state ) );
	}
	switch ( state ) {
		case XR_SESSION_STATE_READY: {
			XrSessionBeginInfo beginInfo;
			memset( &beginInfo, 0, sizeof( beginInfo ) );
			beginInfo.type = XR_TYPE_SESSION_BEGIN_INFO;
			beginInfo.primaryViewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
			if ( Check( xrBeginSession( session, &beginInfo ), "xrBeginSession" ) ) {
				sessionRunning = true;
				lastFrameMsec = Sys_Milliseconds();
				common->Printf( "OpenXR: presenting to the headset\n" );
			}
			break;
		}
		case XR_SESSION_STATE_FOCUSED:
			sessionFocused = true;
			break;
		case XR_SESSION_STATE_VISIBLE:
		case XR_SESSION_STATE_SYNCHRONIZED:
			sessionFocused = false;
			break;
		case XR_SESSION_STATE_STOPPING:
			sessionFocused = false;
			if ( sessionRunning ) {
				xrEndSession( session );
				sessionRunning = false;
				common->Printf( "OpenXR: stopped presenting to the headset\n" );
			}
			break;
		case XR_SESSION_STATE_LOSS_PENDING:
			common->Warning( "OpenXR: the headset session was lost; it reopens when the headset returns" );
			DestroySession();
			break;
		case XR_SESSION_STATE_EXITING:
			// the runtime asked us to leave VR; the game keeps running on the
			// desktop and vr_enable keeps the player's choice for the next launch
			common->Printf( "OpenXR: the runtime ended the VR session; vr_restart starts it again\n" );
			DestroySession();
			DestroyInstance();
			runtimeStopped = true;
			break;
		default:
			break;
	}
}

/*
====================
Pose conversion

Poses arrive in the runtime's LOCAL space. The recentre pose (a heading and
a position) becomes the origin the game sees.
====================
*/
XrPosef idVRSystemOpenXR::RecenteredLocalPose( const XrPosef &pose ) const {
	return VR_PoseMultiply( VR_PoseInverse( recenterPose ), pose );
}

vrPose_t idVRSystemOpenXR::ToEnginePose( const XrPosef &localPose, bool valid ) const {
	vrPose_t out;
	memset( &out, 0, sizeof( out ) );
	out.axis.Identity();
	if ( !valid ) {
		return out;
	}
	const XrPosef pose = RecenteredLocalPose( localPose );
	const float unitsPerMetre = vr_worldScale.GetFloat();
	const vrVec3_t origin = VR_XrToEnginePosition( VR_FromXrVec( pose.position ), unitsPerMetre );
	vrVec3_t axis[3];
	VR_QuatToAxis( VR_XrToEngineOrientation( VR_FromXrQuat( pose.orientation ) ), axis );
	if ( !VR_IsFinite( origin ) || !VR_IsFinite( axis[0] ) ) {
		return out;
	}
	out.valid = true;
	out.origin.Set( origin.x, origin.y, origin.z );
	for ( int i = 0; i < 3; i++ ) {
		out.axis[i].Set( axis[i].x, axis[i].y, axis[i].z );
	}
	return out;
}

/*
====================
idVRSystemOpenXR::LocateFrame
====================
*/
void idVRSystemOpenXR::LocateFrame( XrTime time ) {
	viewsValid = false;
	XrViewLocateInfo locateInfo;
	memset( &locateInfo, 0, sizeof( locateInfo ) );
	locateInfo.type = XR_TYPE_VIEW_LOCATE_INFO;
	locateInfo.viewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
	locateInfo.displayTime = time;
	locateInfo.space = localSpace;
	XrViewState viewState;
	memset( &viewState, 0, sizeof( viewState ) );
	viewState.type = XR_TYPE_VIEW_STATE;
	for ( int i = 0; i < VR_NUM_EYES; i++ ) {
		memset( &views[i], 0, sizeof( views[i] ) );
		views[i].type = XR_TYPE_VIEW;
		views[i].pose = VR_IdentityPose();
	}
	uint32_t viewCount = 0;
	if ( Check( xrLocateViews( session, &locateInfo, &viewState, VR_NUM_EYES, &viewCount, views ), "xrLocateViews" )
			&& viewCount == VR_NUM_EYES && ( viewState.viewStateFlags & XR_VIEW_STATE_ORIENTATION_VALID_BIT ) != 0 ) {
		viewsValid = true;
		if ( ( viewState.viewStateFlags & XR_VIEW_STATE_POSITION_VALID_BIT ) == 0 ) {
			// orientation-only tracking: keep the eyes on a fixed head position
			for ( int i = 0; i < VR_NUM_EYES; i++ ) {
				views[i].pose.position.x = ( i == 0 ? -0.032f : 0.032f );
				views[i].pose.position.y = 0.0f;
				views[i].pose.position.z = 0.0f;
			}
		}
	}

	XrSpaceLocation head;
	memset( &head, 0, sizeof( head ) );
	head.type = XR_TYPE_SPACE_LOCATION;
	const bool headValid = xrLocateSpace( viewSpace, localSpace, time, &head ) == XR_SUCCESS
		&& ( head.locationFlags & XR_SPACE_LOCATION_ORIENTATION_VALID_BIT ) != 0;
	if ( headValid && ( head.locationFlags & XR_SPACE_LOCATION_POSITION_VALID_BIT ) == 0 ) {
		head.pose.position.x = head.pose.position.y = head.pose.position.z = 0.0f;
	}

	if ( recenterRequested && headValid ) {
		recenterPose.orientation = VR_YawOnly( head.pose.orientation );
		recenterPose.position = head.pose.position;
		recenterRequested = false;
		screenAnchored = false;
		Sys_EnterCriticalSection( VR_INPUT_CRITICAL_SECTION );
		bodyYawValid = false;
		Sys_LeaveCriticalSection( VR_INPUT_CRITICAL_SECTION );
		if ( vr_debug.GetInteger() > 0 ) {
			common->Printf( "OpenXR: recentred at ( %.2f %.2f %.2f )\n", head.pose.position.x, head.pose.position.y, head.pose.position.z );
		}
	}

	frame.head = ToEnginePose( head.pose, headValid );
	for ( int i = 0; i < VR_NUM_EYES; i++ ) {
		frame.eyes[i].pose = ToEnginePose( views[i].pose, viewsValid );
		const vrFovTangents_t fov = VR_FovTangentsFromAngles( views[i].fov.angleLeft, views[i].fov.angleRight, views[i].fov.angleUp, views[i].fov.angleDown );
		frame.eyes[i].tanLeft = fov.left;
		frame.eyes[i].tanRight = fov.right;
		frame.eyes[i].tanUp = fov.up;
		frame.eyes[i].tanDown = fov.down;
		if ( !VR_FovTangentsValid( fov ) ) {
			viewsValid = false;
		}
	}

	for ( int hand = 0; hand < VR_NUM_HANDS; hand++ ) {
		XrSpaceLocation location;
		memset( &location, 0, sizeof( location ) );
		location.type = XR_TYPE_SPACE_LOCATION;
		const XrSpaceLocationFlags required = XR_SPACE_LOCATION_ORIENTATION_VALID_BIT | XR_SPACE_LOCATION_POSITION_VALID_BIT;
		bool valid = aimSpaces[hand] != XR_NULL_HANDLE && xrLocateSpace( aimSpaces[hand], localSpace, time, &location ) == XR_SUCCESS
			&& ( location.locationFlags & required ) == required;
		frame.aim[hand] = ToEnginePose( location.pose, valid );
		aimLocalPoses[hand] = valid ? location.pose : VR_IdentityPose();
		aimLocalValid[hand] = valid;
		memset( &location, 0, sizeof( location ) );
		location.type = XR_TYPE_SPACE_LOCATION;
		valid = gripSpaces[hand] != XR_NULL_HANDLE && xrLocateSpace( gripSpaces[hand], localSpace, time, &location ) == XR_SUCCESS
			&& ( location.locationFlags & required ) == required;
		frame.grip[hand] = ToEnginePose( location.pose, valid );
	}
}

/*
====================
Input
====================
*/
bool idVRSystemOpenXR::MenuMode( void ) const {
	return ( console != NULL && console->Active() ) || ( ::session != NULL && ::session->IsGUIActive() ) || RetainedUI_IsOpen();
}

// The off hand's palm is on the gun's foregrip: ahead of the weapon hand's
// palm and close to the line it aims along (VR_OffHandOnForegrip).
bool idVRSystemOpenXR::OffHandOnForegrip( int weaponHand ) const {
	const int offHand = 1 - weaponHand;
	const vrPose_t &aim = frame.aim[weaponHand];
	const vrPose_t &rear = frame.grip[weaponHand];
	const vrPose_t &front = frame.grip[offHand];
	if ( !aim.valid || !rear.valid || !front.valid ) {
		return false;
	}
	return VR_OffHandOnForegrip( VR_Vec3( rear.origin.x, rear.origin.y, rear.origin.z ),
		VR_Vec3( aim.axis[0].x, aim.axis[0].y, aim.axis[0].z ),
		VR_Vec3( front.origin.x, front.origin.y, front.origin.z ), vr_worldScale.GetFloat() );
}

// Two hands on the gun: the weapon hand's aim keeps its origin and roll and
// points from its palm through the other one, so the usercmd, the drawn gun,
// the laser and the shots all follow the steadier two-handed line.
void idVRSystemOpenXR::ApplyTwoHandedAim( int weaponHand ) {
	const int offHand = 1 - weaponHand;
	vrPose_t &aim = frame.aim[weaponHand];
	const vrPose_t &rear = frame.grip[weaponHand];
	const vrPose_t &front = frame.grip[offHand];
	if ( !aim.valid || !rear.valid || !front.valid ) {
		return;
	}
	vrVec3_t rows[3];
	if ( !VR_TwoHandedAxis( VR_Vec3( rear.origin.x, rear.origin.y, rear.origin.z ),
			VR_Vec3( front.origin.x, front.origin.y, front.origin.z ),
			VR_Vec3( aim.axis[2].x, aim.axis[2].y, aim.axis[2].z ), rows ) ) {
		return;
	}
	for ( int i = 0; i < 3; i++ ) {
		aim.axis[i].Set( rows[i].x, rows[i].y, rows[i].z );
	}
}

void idVRSystemOpenXR::PostKey( int key, bool down ) {
	if ( key > 0 ) {
		if ( vr_debug.GetInteger() > 0 ) {
			common->Printf( "OpenXR: %s %s\n", idKeyInput::KeyNumToString( key, false ), down ? "down" : "up" );
		}
		Sys_PostVRControllerKey( key, down );
	}
}

// A key slot remembers which key it pressed, so a release always matches its
// press even if the menu state changed the mapping in between.
void idVRSystemOpenXR::UpdateKey( int slot, int key, bool down ) {
	if ( slot < 0 || slot >= 16 ) {
		return;
	}
	if ( down ) {
		if ( heldKeys[slot] == key ) {
			return;
		}
		if ( heldKeys[slot] != 0 ) {
			PostKey( heldKeys[slot], false );
		}
		heldKeys[slot] = key;
		PostKey( key, true );
	} else if ( heldKeys[slot] != 0 ) {
		PostKey( heldKeys[slot], false );
		heldKeys[slot] = 0;
	}
}

enum vrKeySlot_t {
	VR_SLOT_WEAPON_TRIGGER,
	VR_SLOT_OFF_TRIGGER,
	VR_SLOT_WEAPON_SQUEEZE,
	VR_SLOT_OFF_SQUEEZE,
	VR_SLOT_RIGHT_PRIMARY,
	VR_SLOT_RIGHT_SECONDARY,
	VR_SLOT_LEFT_PRIMARY,
	VR_SLOT_LEFT_SECONDARY,
	VR_SLOT_MENU,
	VR_SLOT_WEAPON_STICK_CLICK,
	VR_SLOT_OFF_STICK_CLICK,
	VR_SLOT_WEAPON_STICK_Y,
	VR_SLOT_MENU_STICK_X,
	VR_SLOT_MENU_STICK_Y
};

void idVRSystemOpenXR::SyncInput( float frameSeconds ) {
	bool synced = false;
	if ( actionsAttached && sessionFocused ) {
		XrActiveActionSet active;
		active.actionSet = actionSet;
		active.subactionPath = XR_NULL_PATH;
		XrActionsSyncInfo syncInfo;
		memset( &syncInfo, 0, sizeof( syncInfo ) );
		syncInfo.type = XR_TYPE_ACTIONS_SYNC_INFO;
		syncInfo.countActiveActionSets = 1;
		syncInfo.activeActionSets = &active;
		const XrResult result = xrSyncActions( session, &syncInfo );
		synced = result == XR_SUCCESS;
		if ( XR_FAILED( result ) ) {
			Check( result, "xrSyncActions" );
		}
	}

	memset( hands, 0, sizeof( hands ) );
	if ( synced ) {
		for ( int hand = 0; hand < VR_NUM_HANDS; hand++ ) {
			XrActionStateGetInfo getInfo;
			memset( &getInfo, 0, sizeof( getInfo ) );
			getInfo.type = XR_TYPE_ACTION_STATE_GET_INFO;
			getInfo.subactionPath = handPaths[hand];

			XrActionStateFloat floatState;
			memset( &floatState, 0, sizeof( floatState ) );
			floatState.type = XR_TYPE_ACTION_STATE_FLOAT;
			getInfo.action = actions[VR_ACTION_TRIGGER];
			if ( xrGetActionStateFloat( session, &getInfo, &floatState ) == XR_SUCCESS && floatState.isActive ) {
				hands[hand].trigger = floatState.currentState;
			}
			getInfo.action = actions[VR_ACTION_SQUEEZE];
			if ( xrGetActionStateFloat( session, &getInfo, &floatState ) == XR_SUCCESS && floatState.isActive ) {
				hands[hand].squeeze = floatState.currentState;
			}

			XrActionStateVector2f vectorState;
			memset( &vectorState, 0, sizeof( vectorState ) );
			vectorState.type = XR_TYPE_ACTION_STATE_VECTOR2F;
			getInfo.action = actions[VR_ACTION_THUMBSTICK];
			if ( xrGetActionStateVector2f( session, &getInfo, &vectorState ) == XR_SUCCESS && vectorState.isActive ) {
				hands[hand].stickX = vectorState.currentState.x;
				hands[hand].stickY = vectorState.currentState.y;
			}

			XrActionStateBoolean boolState;
			memset( &boolState, 0, sizeof( boolState ) );
			boolState.type = XR_TYPE_ACTION_STATE_BOOLEAN;
			getInfo.action = actions[VR_ACTION_THUMBSTICK_CLICK];
			if ( xrGetActionStateBoolean( session, &getInfo, &boolState ) == XR_SUCCESS ) {
				hands[hand].stickClick = boolState.isActive && boolState.currentState;
			}
			getInfo.action = actions[VR_ACTION_PRIMARY];
			if ( xrGetActionStateBoolean( session, &getInfo, &boolState ) == XR_SUCCESS ) {
				hands[hand].primary = boolState.isActive && boolState.currentState;
			}
			getInfo.action = actions[VR_ACTION_SECONDARY];
			if ( xrGetActionStateBoolean( session, &getInfo, &boolState ) == XR_SUCCESS ) {
				hands[hand].secondary = boolState.isActive && boolState.currentState;
			}
			getInfo.action = actions[VR_ACTION_MENU];
			if ( xrGetActionStateBoolean( session, &getInfo, &boolState ) == XR_SUCCESS ) {
				hands[hand].menu = boolState.isActive && boolState.currentState;
			}
		}
	}

	const int weaponHand = vr_leftHanded.GetBool() ? VR_HAND_LEFT : VR_HAND_RIGHT;
	const int offHand = 1 - weaponHand;
	const handInput_t &weapon = hands[weaponHand];
	const handInput_t &off = hands[offHand];
	const bool menu = MenuMode();
	const float deadzone = idMath::ClampFloat( 0.0f, 0.9f, vr_stickDeadzone.GetFloat() );
	UpdateMenuPointer( weaponHand, menu );

	// Buttons are the SDL gamepad's JOY keys (content/baseoq4/pak0/default.cfg):
	// RT attack, LT zoom, A jump, B crouch, X reload, Y flashlight, LB weapon
	// wheel, RB last weapon, Start menu, L3 run, R3 centre view. Menus navigate
	// with the same keys and the D-pad keys below. A trigger pulled while the
	// pointer rests on a menu clicks there instead, and stays a click until it
	// is released.
	const int heldTrigger = heldKeys[VR_SLOT_WEAPON_TRIGGER];
	UpdateKey( VR_SLOT_WEAPON_TRIGGER, heldTrigger != 0 ? heldTrigger : ( pointerOnScreen ? K_MOUSE1 : K_JOY15 ),
		weapon.trigger > ( heldTrigger != 0 ? 0.55f : 0.75f ) );
	UpdateKey( VR_SLOT_OFF_TRIGGER, K_JOY16, off.trigger > ( heldKeys[VR_SLOT_OFF_TRIGGER] ? 0.55f : 0.75f ) );
	UpdateKey( VR_SLOT_WEAPON_SQUEEZE, K_JOY2, weapon.squeeze > ( heldKeys[VR_SLOT_WEAPON_SQUEEZE] ? 0.55f : 0.75f ) );
	// The off-hand squeeze opens the weapon wheel, unless it closes on the
	// gun's foregrip: then it steadies the gun in both hands until released.
	// Which one is decided when the squeeze closes and kept while it is held.
	const bool offSqueezed = off.squeeze > ( ( heldKeys[VR_SLOT_OFF_SQUEEZE] || twoHanded ) ? 0.55f : 0.75f );
	if ( !offSqueezed ) {
		if ( twoHanded && vr_debug.GetInteger() > 0 ) {
			common->Printf( "OpenXR: two-handed aim released\n" );
		}
		twoHanded = false;
	} else if ( !twoHanded && heldKeys[VR_SLOT_OFF_SQUEEZE] == 0 && !menu && vr_twoHanded.GetBool()
			&& vr_aimMode.GetInteger() == VR_AIM_HAND && OffHandOnForegrip( weaponHand ) ) {
		twoHanded = true;
		Vibrate( offHand, 0.35f, 20 );
		if ( vr_debug.GetInteger() > 0 ) {
			common->Printf( "OpenXR: two-handed aim held\n" );
		}
	}
	UpdateKey( VR_SLOT_OFF_SQUEEZE, K_JOY1, offSqueezed && !twoHanded );
	UpdateKey( VR_SLOT_RIGHT_PRIMARY, K_JOY3, hands[VR_HAND_RIGHT].primary );
	UpdateKey( VR_SLOT_RIGHT_SECONDARY, K_JOY4, hands[VR_HAND_RIGHT].secondary );
	UpdateKey( VR_SLOT_LEFT_PRIMARY, K_JOY6, hands[VR_HAND_LEFT].primary );
	UpdateKey( VR_SLOT_LEFT_SECONDARY, K_JOY5, hands[VR_HAND_LEFT].secondary );
	UpdateKey( VR_SLOT_MENU, K_JOY7, hands[VR_HAND_LEFT].menu || hands[VR_HAND_RIGHT].menu );
	UpdateKey( VR_SLOT_WEAPON_STICK_CLICK, K_JOY14, weapon.stickClick );
	UpdateKey( VR_SLOT_OFF_STICK_CLICK, K_JOY13, off.stickClick );

	float turn = 0.0f;
	if ( menu ) {
		// either stick is a D-pad: up, down, right, left
		const float stickX = idMath::Fabs( weapon.stickX ) > idMath::Fabs( off.stickX ) ? weapon.stickX : off.stickX;
		const float stickY = idMath::Fabs( weapon.stickY ) > idMath::Fabs( off.stickY ) ? weapon.stickY : off.stickY;
		UpdateKey( VR_SLOT_WEAPON_STICK_Y, 0, false );
		const int heldY = heldKeys[VR_SLOT_MENU_STICK_Y];
		const int heldX = heldKeys[VR_SLOT_MENU_STICK_X];
		UpdateKey( VR_SLOT_MENU_STICK_Y, stickY > 0.0f ? K_JOY9 : K_JOY10, idMath::Fabs( stickY ) > ( heldY ? 0.35f : 0.75f ) );
		UpdateKey( VR_SLOT_MENU_STICK_X, stickX > 0.0f ? K_JOY11 : K_JOY12, idMath::Fabs( stickX ) > ( heldX ? 0.35f : 0.75f ) );
		snapTurn.latched = true;
	} else {
		UpdateKey( VR_SLOT_MENU_STICK_X, 0, false );
		UpdateKey( VR_SLOT_MENU_STICK_Y, 0, false );
		// weapon stick up / down pages weapons (JOY12 next, JOY11 previous)
		const int held = heldKeys[VR_SLOT_WEAPON_STICK_Y];
		UpdateKey( VR_SLOT_WEAPON_STICK_Y, weapon.stickY > 0.0f ? K_JOY12 : K_JOY11, idMath::Fabs( weapon.stickY ) > ( held ? 0.35f : 0.75f )
			&& idMath::Fabs( weapon.stickY ) > idMath::Fabs( weapon.stickX ) );
		if ( vr_turnMode.GetInteger() == 1 ) {
			turn = VR_SmoothTurn( weapon.stickX, vr_smoothTurnSpeed.GetFloat(), frameSeconds, deadzone );
		} else {
			turn = VR_SnapTurn( snapTurn, weapon.stickX, vr_snapTurnAngle.GetFloat() );
		}
	}

	// two hands on the gun: it points from the rear palm through the front one
	if ( twoHanded && !menu ) {
		ApplyTwoHandedAim( weaponHand );
	}

	// aim: the weapon hand's pointing ray, or the head
	const vrPose_t &aimPose = ( vr_aimMode.GetInteger() == VR_AIM_HAND && frame.aim[weaponHand].valid ) ? frame.aim[weaponHand] : frame.head;
	float localYaw = aimLocalYaw;
	float localPitch = aimLocalPitch;
	if ( aimPose.valid ) {
		const vrVec3_t forward = VR_Vec3( aimPose.axis[0].x, aimPose.axis[0].y, aimPose.axis[0].z );
		localYaw = VR_YawDegrees( forward );
		localPitch = idMath::ClampFloat( -89.0f, 89.0f, VR_PitchDegrees( forward ) );
	}

	// locomotion: the off-hand stick, relative to the head or the off-hand
	// controller, expressed in the aim frame the usercmd moves along
	float forwardMove = 0.0f, rightMove = 0.0f;
	if ( !menu ) {
		const float stickX = VR_ApplyDeadzone( off.stickX, deadzone );
		const float stickY = VR_ApplyDeadzone( off.stickY, deadzone );
		if ( stickX != 0.0f || stickY != 0.0f ) {
			const vrPose_t &reference = ( vr_moveDirection.GetInteger() == 1 && frame.aim[offHand].valid ) ? frame.aim[offHand] : frame.head;
			const float referenceYaw = reference.valid
				? VR_YawDegrees( VR_Vec3( reference.axis[0].x, reference.axis[0].y, reference.axis[0].z ) ) : localYaw;
			const float delta = DEG2RAD( referenceYaw - localYaw );
			const float c = idMath::Cos( delta ), s = idMath::Sin( delta );
			// stick +Y forward, +X right; the engine's left is -right
			const float forwardRef = stickY, leftRef = -stickX;
			const float forwardAim = c * forwardRef - s * leftRef;
			const float leftAim = s * forwardRef + c * leftRef;
			forwardMove = idMath::ClampFloat( -1.0f, 1.0f, forwardAim );
			rightMove = idMath::ClampFloat( -1.0f, 1.0f, -leftAim );
		}
	}

	Sys_EnterCriticalSection( VR_INPUT_CRITICAL_SECTION );
	inputValid = sessionRunning && sessionFocused;
	if ( bodyYawValid ) {
		bodyYaw = VR_NormalizeDegrees180( bodyYaw + turn );
	}
	aimLocalYaw = localYaw;
	aimLocalPitch = localPitch;
	moveForward = forwardMove;
	moveRight = rightMove;
	frame.bodyYaw = bodyYaw;
	Sys_LeaveCriticalSection( VR_INPUT_CRITICAL_SECTION );
}

bool idVRSystemOpenXR::GetUsercmdInput( float otherYawDelta, float currentYaw, vrUsercmdInput_t &input ) {
	memset( &input, 0, sizeof( input ) );
	Sys_EnterCriticalSection( VR_INPUT_CRITICAL_SECTION );
	if ( !inputValid ) {
		Sys_LeaveCriticalSection( VR_INPUT_CRITICAL_SECTION );
		return false;
	}
	if ( !bodyYawValid ) {
		// keep the current aim continuous when VR takes over
		bodyYaw = VR_NormalizeDegrees180( currentYaw - aimLocalYaw );
		bodyYawValid = true;
	} else {
		// the mouse, keys or a gamepad turned this tic: that turns the body
		bodyYaw = VR_NormalizeDegrees180( bodyYaw + otherYawDelta );
	}
	input.aimYaw = bodyYaw + aimLocalYaw;
	input.aimPitch = aimLocalPitch;
	input.forward = moveForward;
	input.right = moveRight;
	Sys_LeaveCriticalSection( VR_INPUT_CRITICAL_SECTION );
	return true;
}

/*
====================
idVRSystemOpenXR::GetFrameState
====================
*/
void idVRSystemOpenXR::GetFrameState( vrFrameState_t &state ) const {
	Sys_EnterCriticalSection( VR_INPUT_CRITICAL_SECTION );
	state = frame;
	state.bodyYaw = bodyYaw;
	Sys_LeaveCriticalSection( VR_INPUT_CRITICAL_SECTION );
}

/*
====================
Frame loop
====================
*/
bool idVRSystemOpenXR::AcquireImages( void ) {
	swapchain_t *chains[3] = { &screenSwapchain, &eyeSwapchains[0], &eyeSwapchains[1] };
	bool ok = true;
	for ( int i = 0; i < 3; i++ ) {
		swapchain_t &chain = *chains[i];
		chain.acquired = false;
		if ( chain.handle == XR_NULL_HANDLE ) {
			ok = false;
			continue;
		}
		XrSwapchainImageAcquireInfo acquireInfo;
		memset( &acquireInfo, 0, sizeof( acquireInfo ) );
		acquireInfo.type = XR_TYPE_SWAPCHAIN_IMAGE_ACQUIRE_INFO;
		uint32_t index = 0;
		if ( !Check( xrAcquireSwapchainImage( chain.handle, &acquireInfo, &index ), "xrAcquireSwapchainImage" ) ) {
			ok = false;
			continue;
		}
		XrSwapchainImageWaitInfo waitInfo;
		memset( &waitInfo, 0, sizeof( waitInfo ) );
		waitInfo.type = XR_TYPE_SWAPCHAIN_IMAGE_WAIT_INFO;
		waitInfo.timeout = XR_INFINITE_DURATION;
		if ( !Check( xrWaitSwapchainImage( chain.handle, &waitInfo ), "xrWaitSwapchainImage" ) ) {
			// an acquired image must still be released
			XrSwapchainImageReleaseInfo releaseInfo;
			memset( &releaseInfo, 0, sizeof( releaseInfo ) );
			releaseInfo.type = XR_TYPE_SWAPCHAIN_IMAGE_RELEASE_INFO;
			xrReleaseSwapchainImage( chain.handle, &releaseInfo );
			ok = false;
			continue;
		}
		if ( static_cast<int>( index ) >= chain.images.Num() ) {
			ok = false;
		}
		chain.acquiredIndex = index;
		chain.acquired = true;
	}
	return ok;
}

void idVRSystemOpenXR::ReleaseImages( void ) {
	swapchain_t *chains[3] = { &screenSwapchain, &eyeSwapchains[0], &eyeSwapchains[1] };
	for ( int i = 0; i < 3; i++ ) {
		swapchain_t &chain = *chains[i];
		if ( !chain.acquired || chain.handle == XR_NULL_HANDLE ) {
			chain.acquired = false;
			continue;
		}
		XrSwapchainImageReleaseInfo releaseInfo;
		memset( &releaseInfo, 0, sizeof( releaseInfo ) );
		releaseInfo.type = XR_TYPE_SWAPCHAIN_IMAGE_RELEASE_INFO;
		Check( xrReleaseSwapchainImage( chain.handle, &releaseInfo ), "xrReleaseSwapchainImage" );
		chain.acquired = false;
	}
}

/*
====================
Virtual screen

Menus, the HUD and their pointer all lay out for the window's 2D viewport, so
the virtual screen takes its aspect (4:3 through 32:9) at a fixed width;
another shape would stretch them.
====================
*/
void idVRSystemOpenXR::ScreenSizeForWindow( int &width, int &height ) const {
	width = VR_SCREEN_WIDTH;
	height = VR_SCREEN_HEIGHT;
	if ( engineWindowState.uiViewportWidth > 0 && engineWindowState.uiViewportHeight > 0 ) {
		const float aspect = static_cast<float>( engineWindowState.uiViewportWidth ) / static_cast<float>( engineWindowState.uiViewportHeight );
		height = idMath::Ftoi( static_cast<float>( VR_SCREEN_WIDTH ) / idMath::ClampFloat( 4.0f / 3.0f, 32.0f / 9.0f, aspect ) ) & ~1;
	}
}

// Follows a window resize between frames; a failed size is not retried until
// the window changes again.
bool idVRSystemOpenXR::ResizeScreenSwapchain( void ) {
	int width = 0, height = 0;
	ScreenSizeForWindow( width, height );
	if ( screenSwapchain.handle != XR_NULL_HANDLE && width == screenSwapchain.width && height == screenSwapchain.height ) {
		return true;
	}
	if ( width == screenResizeFailedWidth && height == screenResizeFailedHeight ) {
		return screenSwapchain.handle != XR_NULL_HANDLE;
	}
	swapchain_t resized;
	resized.handle = XR_NULL_HANDLE;
	resized.width = resized.height = 0;
	resized.acquiredIndex = 0;
	resized.acquired = false;
	if ( !CreateSwapchain( resized, width, height ) ) {
		screenResizeFailedWidth = width;
		screenResizeFailedHeight = height;
		return screenSwapchain.handle != XR_NULL_HANDLE;
	}
	DestroySwapchain( screenSwapchain );
	screenSwapchain.handle = resized.handle;
	screenSwapchain.width = resized.width;
	screenSwapchain.height = resized.height;
	screenSwapchain.images = resized.images;
	screenSwapchain.acquiredIndex = 0;
	screenSwapchain.acquired = false;
	screenResizeFailedWidth = screenResizeFailedHeight = 0;
	if ( vr_debug.GetInteger() > 0 ) {
		common->Printf( "OpenXR: virtual screen %dx%d\n", width, height );
	}
	return true;
}

void idVRSystemOpenXR::ScreenQuadSize( float &width, float &height ) const {
	width = idMath::ClampFloat( 0.5f, 12.0f, vr_screenWidth.GetFloat() );
	height = width * static_cast<float>( screenSwapchain.height ) / static_cast<float>( Max( 1, screenSwapchain.width ) );
}

/*
====================
idVRSystemOpenXR::UpdateMenuPointer

In menus the weapon hand points at the virtual screen like a mouse. A small
dead band keeps hand tremor from re-hovering the menu every frame, which
would also take focus from stick navigation.
====================
*/
void idVRSystemOpenXR::UpdateMenuPointer( int weaponHand, bool menu ) {
	const bool wasOnScreen = pointerOnScreen;
	pointerOnScreen = false;
	// the screen re-anchors on the first menu frame: point from the next one
	if ( !menu || !screenAnchored || lastFrameHud || !aimLocalValid[weaponHand] ) {
		if ( wasOnScreen && menu ) {
			Sys_PostVRPointer( false, 0.0f, 0.0f );
		}
		return;
	}
	float width = 0.0f, height = 0.0f;
	ScreenQuadSize( width, height );
	const XrPosef &aim = aimLocalPoses[weaponHand];
	const vrVec3_t direction = VR_RotateVector( VR_FromXrQuat( aim.orientation ), VR_Vec3( 0.0f, 0.0f, -1.0f ) );
	const vrQuadHit_t hit = VR_RayQuadIntersect( VR_FromXrVec( aim.position ), direction,
		VR_FromXrVec( screenAnchor.position ), VR_FromXrQuat( screenAnchor.orientation ), width, height );
	if ( !hit.hit ) {
		if ( wasOnScreen ) {
			Sys_PostVRPointer( false, 0.0f, 0.0f );
		}
		return;
	}
	const float deadBand = 0.0015f;
	if ( wasOnScreen && idMath::Fabs( hit.u - pointerU ) < deadBand && idMath::Fabs( hit.v - pointerV ) < deadBand ) {
		pointerOnScreen = true;
		return;
	}
	if ( Sys_PostVRPointer( true, hit.u, hit.v ) ) {
		pointerOnScreen = true;
		pointerU = hit.u;
		pointerV = hit.v;
	}
}

/*
====================
idVRSystemOpenXR::ShiftTrackingOrigin

The recentre pose (a heading and a position in LOCAL space) moves by the
distance the body walked, horizontally only, and the poses already handed
out for this frame move with it, so the camera stays on the head.
====================
*/
void idVRSystemOpenXR::ShiftTrackingOrigin( const idVec3 &trackingDelta ) {
	const float unitsPerMetre = vr_worldScale.GetFloat();
	if ( !sessionRunning || unitsPerMetre <= 0.0f || !VR_IsFinite( VR_Vec3( trackingDelta.x, trackingDelta.y, trackingDelta.z ) ) ) {
		return;
	}
	const idVec3 horizontal( trackingDelta.x, trackingDelta.y, 0.0f );
	const vrVec3_t xr = VR_Scale( VR_EngineToXrDirection( VR_Vec3( horizontal.x, horizontal.y, 0.0f ) ), 1.0f / unitsPerMetre );
	const vrVec3_t local = VR_RotateVector( VR_QuatNormalize( VR_FromXrQuat( recenterPose.orientation ) ), xr );
	recenterPose.position.x += local.x;
	recenterPose.position.y += local.y;
	recenterPose.position.z += local.z;
	Sys_EnterCriticalSection( VR_INPUT_CRITICAL_SECTION );
	frame.head.origin -= horizontal;
	for ( int i = 0; i < VR_NUM_EYES; i++ ) {
		frame.eyes[i].pose.origin -= horizontal;
	}
	for ( int i = 0; i < VR_NUM_HANDS; i++ ) {
		frame.grip[i].origin -= horizontal;
		frame.aim[i].origin -= horizontal;
	}
	Sys_LeaveCriticalSection( VR_INPUT_CRITICAL_SECTION );
}

/*
====================
idVRSystemOpenXR::Vibrate
====================
*/
void idVRSystemOpenXR::Vibrate( int hand, float amplitude, int durationMsec ) {
	if ( !sessionRunning || !sessionFocused || !actionsAttached || hand < 0 || hand >= VR_NUM_HANDS || durationMsec <= 0 ) {
		return;
	}
	const float strength = idMath::ClampFloat( 0.0f, 1.0f, amplitude ) * idMath::ClampFloat( 0.0f, 1.0f, vr_hapticStrength.GetFloat() );
	if ( strength <= 0.0f ) {
		return;
	}
	XrHapticActionInfo info;
	memset( &info, 0, sizeof( info ) );
	info.type = XR_TYPE_HAPTIC_ACTION_INFO;
	info.action = actions[VR_ACTION_HAPTIC];
	info.subactionPath = handPaths[hand];
	XrHapticVibration vibration;
	memset( &vibration, 0, sizeof( vibration ) );
	vibration.type = XR_TYPE_HAPTIC_VIBRATION;
	vibration.duration = static_cast<XrDuration>( Min( durationMsec, 2000 ) ) * 1000000;
	vibration.frequency = XR_FREQUENCY_UNSPECIFIED;
	vibration.amplitude = strength;
	Check( xrApplyHapticFeedback( session, &info, reinterpret_cast<const XrHapticBaseHeader *>( &vibration ) ), "xrApplyHapticFeedback" );
}

/*
====================
idVRSystemOpenXR::DrawMenuPointer

A ringed dot over everything else in the 2D pass; stock menus also move their
own cursor to it.
====================
*/
void idVRSystemOpenXR::DrawMenuPointer( void ) {
	if ( !frame.active || !pointerOnScreen || screenSwapchain.width <= 0 || screenSwapchain.height <= 0 ) {
		return;
	}
	if ( pointerMaterial == NULL ) {
		pointerMaterial = declManager->FindMaterial( "_white" );
	}
	// the 640x480 canvas stretches over the screen: keep the dot square
	const float aspect = static_cast<float>( screenSwapchain.width ) / static_cast<float>( screenSwapchain.height );
	const float height = 7.0f;
	const float width = height * ( 4.0f / 3.0f ) / aspect;
	const float x = pointerU * static_cast<float>( SCREEN_WIDTH );
	const float y = pointerV * static_cast<float>( SCREEN_HEIGHT );
	renderSystem->SetColor4( 0.0f, 0.0f, 0.0f, 0.8f );
	renderSystem->DrawStretchPic( x - width, y - height, width * 2.0f, height * 2.0f, 0.0f, 0.0f, 1.0f, 1.0f, pointerMaterial );
	renderSystem->SetColor4( 1.0f, 1.0f, 1.0f, 1.0f );
	renderSystem->DrawStretchPic( x - width * 0.5f, y - height * 0.5f, width, height, 0.0f, 0.0f, 1.0f, 1.0f, pointerMaterial );
}

// The virtual screen hangs straight ahead of the head's current heading, at
// eye height, whenever the view leaves gameplay.
void idVRSystemOpenXR::AnchorScreen( void ) {
	XrSpaceLocation head;
	memset( &head, 0, sizeof( head ) );
	head.type = XR_TYPE_SPACE_LOCATION;
	XrPosef base = recenterPose;
	if ( frameDisplayTime > 0 && xrLocateSpace( viewSpace, localSpace, frameDisplayTime, &head ) == XR_SUCCESS
			&& ( head.locationFlags & XR_SPACE_LOCATION_ORIENTATION_VALID_BIT ) != 0 ) {
		base.orientation = VR_YawOnly( head.pose.orientation );
		if ( ( head.locationFlags & XR_SPACE_LOCATION_POSITION_VALID_BIT ) != 0 ) {
			base.position = head.pose.position;
		}
	}
	XrPosef offset = VR_IdentityPose();
	offset.position.z = -idMath::ClampFloat( 0.8f, 10.0f, vr_screenDistance.GetFloat() );
	screenAnchor = VR_PoseMultiply( base, offset );
	screenAnchored = true;
}

void idVRSystemOpenXR::BeginFrame( void ) {
	renderSystem->SetVRFrame( NULL );
	frame.active = false;
	frame.stereo = false;

	StartIfRequested();
	if ( instance != XR_NULL_HANDLE ) {
		PollEvents();
	}
	if ( session == XR_NULL_HANDLE || !sessionRunning ) {
		return;
	}

	XrFrameWaitInfo waitInfo;
	memset( &waitInfo, 0, sizeof( waitInfo ) );
	waitInfo.type = XR_TYPE_FRAME_WAIT_INFO;
	XrFrameState frameState;
	memset( &frameState, 0, sizeof( frameState ) );
	frameState.type = XR_TYPE_FRAME_STATE;
	if ( !Check( xrWaitFrame( session, &waitInfo, &frameState ), "xrWaitFrame" ) ) {
		return;
	}
	XrFrameBeginInfo beginInfo;
	memset( &beginInfo, 0, sizeof( beginInfo ) );
	beginInfo.type = XR_TYPE_FRAME_BEGIN_INFO;
	if ( !Check( xrBeginFrame( session, &beginInfo ), "xrBeginFrame" ) ) {
		return;
	}
	frameOpen = true;
	frameShouldRender = frameState.shouldRender == XR_TRUE;
	frameDisplayTime = frameState.predictedDisplayTime;

	const int now = Sys_Milliseconds();
	const float frameSeconds = idMath::ClampFloat( 0.0f, 0.1f, ( now - lastFrameMsec ) * 0.001f );
	lastFrameMsec = now;

	LocateFrame( frameDisplayTime );
	SyncInput( frameSeconds );

	frame.frameNumber++;
	frame.focused = sessionFocused;
	frame.aimMode = vr_aimMode.GetInteger();
	frame.weaponHand = vr_leftHanded.GetBool() ? VR_HAND_LEFT : VR_HAND_RIGHT;
	frame.unitsPerMetre = vr_worldScale.GetFloat();
	frame.headOffsetLimit = vr_headOffsetLimit.GetFloat();
	frame.weaponOffset.Set( vr_weaponOffsetX.GetFloat(), vr_weaponOffsetY.GetFloat(), vr_weaponOffsetZ.GetFloat() );
	frame.weaponPitch = vr_weaponPitch.GetFloat();
	frame.aimLaser = idMath::ClampInt( VR_AIM_LASER_OFF, VR_AIM_LASER_BEAM, vr_aimLaser.GetInteger() );
	frame.roomScale = vr_roomScale.GetBool();

	if ( !frameShouldRender || !ResizeScreenSwapchain() || !AcquireImages() ) {
		return;
	}

	renderVRFrame_t renderFrame;
	memset( &renderFrame, 0, sizeof( renderFrame ) );
	renderFrame.active = true;
	renderFrame.stereo = viewsValid;
	renderFrame.eyeWidth = eyeSwapchains[0].width;
	renderFrame.eyeHeight = eyeSwapchains[0].height;
	for ( int i = 0; i < VR_NUM_EYES; i++ ) {
		renderFrame.eyeImages[i] = eyeSwapchains[i].images[ static_cast<int>( eyeSwapchains[i].acquiredIndex ) ];
	}
	renderFrame.screenWidth = screenSwapchain.width;
	renderFrame.screenHeight = screenSwapchain.height;
	renderFrame.screenImage = screenSwapchain.images[ static_cast<int>( screenSwapchain.acquiredIndex ) ];
	renderFrame.mirror = idMath::ClampInt( RENDER_VR_MIRROR_NONE, RENDER_VR_MIRROR_SCREEN, vr_mirror.GetInteger() );
	renderSystem->SetVRFrame( &renderFrame );

	frame.active = true;
	frame.stereo = viewsValid;
}

void idVRSystemOpenXR::EndFrame( void ) {
	if ( !frameOpen ) {
		return;
	}
	frameOpen = false;
	ReleaseImages();
	renderSystem->SetVRFrame( NULL );

	renderVRFrameResult_t result;
	memset( &result, 0, sizeof( result ) );
	if ( frame.active ) {
		renderSystem->GetVRFrameResult( result );
	}

	XrCompositionLayerProjectionView projectionViews[VR_NUM_EYES];
	XrCompositionLayerProjection projection;
	XrCompositionLayerQuad quad;
	const XrCompositionLayerBaseHeader *layers[2];
	uint32_t layerCount = 0;

	const bool stereo = result.presented && result.eyeRendered[0] && result.eyeRendered[1] && viewsValid;
	if ( stereo ) {
		for ( int i = 0; i < VR_NUM_EYES; i++ ) {
			memset( &projectionViews[i], 0, sizeof( projectionViews[i] ) );
			projectionViews[i].type = XR_TYPE_COMPOSITION_LAYER_PROJECTION_VIEW;
			projectionViews[i].pose = views[i].pose;
			projectionViews[i].fov = views[i].fov;
			projectionViews[i].subImage.swapchain = eyeSwapchains[i].handle;
			projectionViews[i].subImage.imageRect.offset.x = 0;
			projectionViews[i].subImage.imageRect.offset.y = 0;
			projectionViews[i].subImage.imageRect.extent.width = eyeSwapchains[i].width;
			projectionViews[i].subImage.imageRect.extent.height = eyeSwapchains[i].height;
		}
		memset( &projection, 0, sizeof( projection ) );
		projection.type = XR_TYPE_COMPOSITION_LAYER_PROJECTION;
		projection.space = localSpace;
		projection.viewCount = VR_NUM_EYES;
		projection.views = projectionViews;
		layers[layerCount++] = reinterpret_cast<const XrCompositionLayerBaseHeader *>( &projection );
	}

	if ( result.presented ) {
		// gameplay keeps the HUD in view; menus, loading and cinematics get a
		// screen that stays where it was hung
		const bool hud = stereo && !MenuMode();
		float screenWidth = 0.0f, screenHeight = 0.0f;
		ScreenQuadSize( screenWidth, screenHeight );
		memset( &quad, 0, sizeof( quad ) );
		quad.type = XR_TYPE_COMPOSITION_LAYER_QUAD;
		quad.eyeVisibility = XR_EYE_VISIBILITY_BOTH;
		quad.subImage.swapchain = screenSwapchain.handle;
		quad.subImage.imageRect.extent.width = screenSwapchain.width;
		quad.subImage.imageRect.extent.height = screenSwapchain.height;
		if ( hud ) {
			quad.layerFlags = XR_COMPOSITION_LAYER_BLEND_TEXTURE_SOURCE_ALPHA_BIT;
			quad.space = viewSpace;
			quad.pose = VR_IdentityPose();
			// head aim draws the HUD crosshair: keep it on the line of sight
			quad.pose.position.y = vr_aimMode.GetInteger() == VR_AIM_HAND ? vr_hudHeightOffset.GetFloat() : 0.0f;
			quad.pose.position.z = -idMath::ClampFloat( 0.5f, 5.0f, vr_hudDistance.GetFloat() );
			quad.size.width = idMath::ClampFloat( 0.3f, 4.0f, vr_hudWidth.GetFloat() );
			quad.size.height = quad.size.width * screenHeight / screenWidth;
		} else {
			if ( !screenAnchored || lastFrameHud ) {
				AnchorScreen();
			}
			quad.space = localSpace;
			quad.pose = screenAnchor;
			quad.size.width = screenWidth;
			quad.size.height = screenHeight;
		}
		layers[layerCount++] = reinterpret_cast<const XrCompositionLayerBaseHeader *>( &quad );
		lastFrameHud = hud;
	}

	XrFrameEndInfo endInfo;
	memset( &endInfo, 0, sizeof( endInfo ) );
	endInfo.type = XR_TYPE_FRAME_END_INFO;
	endInfo.displayTime = frameDisplayTime;
	endInfo.environmentBlendMode = blendMode;
	endInfo.layerCount = layerCount;
	endInfo.layers = layerCount > 0 ? layers : NULL;
	Check( xrEndFrame( session, &endInfo ), "xrEndFrame" );
	if ( vr_debug.GetInteger() > 1 ) {
		common->Printf( "OpenXR: frame %d submitted %u layers (stereo %d)\n", frame.frameNumber, layerCount, stereo ? 1 : 0 );
	}
}

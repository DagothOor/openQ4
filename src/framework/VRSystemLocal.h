// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#ifndef __VRSYSTEMLOCAL_H__
#define __VRSYSTEMLOCAL_H__

/*
===============================================================================

	Engine-only VR declarations: the settings every engine target registers
	(VRSystem.cpp), shared by the OpenXR implementation (src/sys/openxr) and
	the usercmd generator. Game modules see only VRSystem.h.

===============================================================================
*/

extern idCVar vr_enable;
extern idCVar vr_renderScale;
extern idCVar vr_worldScale;
extern idCVar vr_aimMode;
extern idCVar vr_leftHanded;
extern idCVar vr_moveDirection;
extern idCVar vr_turnMode;
extern idCVar vr_snapTurnAngle;
extern idCVar vr_smoothTurnSpeed;
extern idCVar vr_stickDeadzone;
extern idCVar vr_headOffsetLimit;
extern idCVar vr_hudDistance;
extern idCVar vr_hudWidth;
extern idCVar vr_hudHeightOffset;
extern idCVar vr_screenDistance;
extern idCVar vr_screenWidth;
extern idCVar vr_mirror;
extern idCVar vr_weaponOffsetX;
extern idCVar vr_weaponOffsetY;
extern idCVar vr_weaponOffsetZ;
extern idCVar vr_weaponPitch;
extern idCVar vr_roomScale;
extern idCVar vr_hapticStrength;
extern idCVar vr_aimLaser;
extern idCVar vr_debug;

// The OpenXR implementation, when the client was built with it (OPENQ4_OPENXR).
idVRSystem *		VR_GetOpenXRSystem( void );

#endif /* !__VRSYSTEMLOCAL_H__ */

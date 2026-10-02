// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
//

/*
===============================================================================

	OpenXR presentation is OpenGL-only for now (XR_KHR_vulkan_enable2 would
	have the runtime create the instance and device; see
	docs/dev/plans/2026-10-02-openxr-vr.md). The shared front end still links
	the presentation entry points, so the Vulkan module reports that it cannot
	present and keeps the window as the only default target.

===============================================================================
*/

#ifdef OPENQ4_RENDERER_VK_MODULE

#include "../../idlib/precompiled.h"
#pragma hdrstop

#include "../tr_local.h"

bool R_VR_BackendCanPresent( void ) {
	return false;
}

bool R_VR_QueryGraphicsBinding( renderVRGraphicsBinding_t &binding ) {
	memset( &binding, 0, sizeof( binding ) );
	return false;
}

void RB_VR_BeginBackEnd( void ) {
}

void RB_VR_SetTarget( const void *data ) {
	(void)data;
}

bool RB_VR_PresentFrame( void ) {
	return false;
}

void R_VR_ShutdownTargets( void ) {
}

void R_SetDefaultRenderTarget( idRenderTexture *target ) {
	(void)target;
}

idRenderTexture *R_GetDefaultRenderTarget( void ) {
	return NULL;
}

unsigned int R_DefaultFramebufferHandle( void ) {
	return 0;
}

unsigned int R_DefaultColorBuffer( void ) {
	return GL_BACK;
}

void R_SetDefaultDrawAndReadBuffers( void ) {
}

void R_SetDefaultRenderTargetPremultiplied( bool premultiplied ) {
	(void)premultiplied;
}

bool R_PremultipliedDefaultTargetBound( void ) {
	return false;
}

#endif // OPENQ4_RENDERER_VK_MODULE

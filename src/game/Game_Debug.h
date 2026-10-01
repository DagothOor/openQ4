//----------------------------------------------------------------
// Game_Debug.h
//
// Copyright 2002-2004 Raven Software
//----------------------------------------------------------------

#ifndef __GAME_DEBUG_H__
#define	__GAME_DEBUG_H__

#define DBGHUD_NONE			(0u)
#define DBGHUD_PLAYER		(1u<<0)
#define DBGHUD_PHYSICS		(1u<<1)
#define DBGHUD_AI			(1u<<2)
#define DBGHUD_VEHICLE		(1u<<3)
#define DBGHUD_PERFORMANCE	(1u<<4)
#define DBGHUD_FX			(1u<<5)
#define DBGHUD_MAPINFO		(1u<<6)
#define DBGHUD_AI_PERFORM	(1u<<7)
#define DBGHUD_SCRATCH		(1u<<31)
#define DBGHUD_ANY			(0xFFFFFFFFu)

#define DBGHUD_MAX			32

typedef struct debugJumpPoint_s 
{
	idStr					name;
	idVec3					origin;
	idAngles				angles;
	
} debugJumpPoint_t;

class rvGameDebug {
public:
	
	rvGameDebug( );
	
	void		Init				( void );
	void		Shutdown			( void );
	void		BeginFrame			( void );
	void		EndFrame			( void );
	
	void		SetFocusEntity		( idEntity* focusEnt );
	
	bool		IsHudActive			( unsigned int hudMask, const idEntity* focusEnt = NULL );
	
	void		DrawHud				( void );
	
	void		AppendList			( const char* listname, const char* value );
	
	void		SetInt				( const char* key, int value );
	void		SetFloat			( const char* key, float value );
	void		SetString			( const char* key, const char* value );
	
	int			GetInt				( const char* key );
	float		GetFloat			( const char* key );
	const char*	GetString			( const char* key );

	void		SetStatInt			( const char* key, int value );
	void		SetStatFloat		( const char* key, float value );
	void		SetStatString		( const char* key, const char* value );
	
	int			GetStatInt			( const char* key );
	float		GetStatFloat		( const char* key );
	const char*	GetStatString		( const char* key );

	void		JumpAdd				( const char* name, const idVec3& origin, const idAngles& angles );
	void		JumpTo				( const char* name );
	void		JumpTo				( int jumpIndex );
	void		JumpNext			( void );
	void		JumpPrev			( void );	
	
private:		

	idList<debugJumpPoint_t>	jumpPoints;
	int							jumpIndex;
	
	idEntityPtr<idEntity>		focusEntity;
	idEntityPtr<idEntity>		overrideEntity;		
	idUserInterface *			hud[DBGHUD_MAX+1];
	idUserInterface *			currentHud;
	idDict						nonGameState, gameStats;
	bool						inFrame;
};

ID_INLINE bool rvGameDebug::IsHudActive ( unsigned int hudMask, const idEntity* ent ) {
	const int hudIndex = g_showDebugHud.GetInteger();
	return hudIndex > 0 && hudIndex <= DBGHUD_MAX &&
		( hudMask & ( 1u << ( hudIndex - 1 ) ) ) != 0 && ( !ent || focusEntity == ent );
}

ID_INLINE void rvGameDebug::SetFocusEntity ( idEntity* ent ) {
	overrideEntity = ent;
}

extern rvGameDebug		gameDebug;

#endif	/* !__GAME_DEBUG_H__ */

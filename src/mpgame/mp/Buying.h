//----------------------------------------------------------------
// Buying.h
//
// Copyright 2005 Ritual Entertainment
//
// This file essentially serves as an extension to the Game DLL
// source files Multiplayer.h and Player.h, in an attempt
// to isolate, as much as possible, these changes from the main
// body of code (for merge simplification, etc).
//----------------------------------------------------------------

#ifndef __BUYING_H__
#define __BUYING_H__

#include "../Game_local.h"
#include "../MultiplayerGame.h"

// jmarshall - the engine UsercmdGen.h only carries the IMPULSE_100/IMPULSE_127
// buy-menu range bounds; the individual buy impulses stay game-local.
const int IMPULSE_101			= 101;			// Buy weapon_machinegun
const int IMPULSE_102			= 102;			// Buy weapon_hyperblaster
const int IMPULSE_103			= 103;			// Buy weapon_grenadelauncher
const int IMPULSE_104			= 104;			// Buy weapon_nailgun
const int IMPULSE_105			= 105;			// Buy weapon_rocketlauncher
const int IMPULSE_106			= 106;			// Buy weapon_railgun
const int IMPULSE_107			= 107;			// Buy weapon_lightninggun
const int IMPULSE_108			= 108;			// UNUSED
const int IMPULSE_109			= 109;			// Buy weapon_napalmgun
const int IMPULSE_110			= 110;			// Buy weapon_dmg
const int IMPULSE_111			= 111;			// UNUSED
const int IMPULSE_112			= 112;			// UNUSED
const int IMPULSE_113			= 113;			// UNUSED
const int IMPULSE_114			= 114;			// UNUSED
const int IMPULSE_115			= 115;			// UNUSED
const int IMPULSE_116			= 116;			// UNUSED
const int IMPULSE_117			= 117;			// UNUSED
const int IMPULSE_118			= 118;			// Buy item_armor_small
const int IMPULSE_119			= 119;			// Buy item_armor_large
const int IMPULSE_120			= 120;			// Buy ammorefill
const int IMPULSE_121			= 121;			// UNUSED
const int IMPULSE_122			= 122;			// UNUSED
const int IMPULSE_123			= 123;			// Buy team powerup: ammo_regen
const int IMPULSE_124			= 124;			// Buy team powerup: health_regen
const int IMPULSE_125			= 125;			// Buy team powerup: damage_boost
const int IMPULSE_126			= 126;			// UNUSED
// jmarshall end

class riBuyingManager
{
private:
	const idDeclEntityDef*	_buyingGameBalanceConstants;
	int						opponentKillCashAward;	// latch
	int						opponentKillFragCount;

public:
	riBuyingManager();
	~riBuyingManager();

	int GetIntValueForKey( const char* keyName, int defaultValue );
	int GetOpponentKillCashAward( void );

	void Reset( void ) { opponentKillFragCount = -1; }
};


#endif // __BUYING_H__

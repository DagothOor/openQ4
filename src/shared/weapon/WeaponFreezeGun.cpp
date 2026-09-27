#include "../../Game_local.h"
#include "../../Weapon.h"

/*
===============================================================================

	rvWeaponFreezeGun

	A short-range freezing spray built on the hyperblaster's body: every shot
	throws five short-fused projectile_freezegun bolts. Its damage defs carry
	"filter_freeze", which puts out func_fire_volume fires, and its projectile
	carries "freezeEnemies". Ammo regenerates through the weapon def's
	ammoRegenStep/ammoRegenTime; the battery glow (shader parm 6) shows how
	full it is.

===============================================================================
*/

class rvWeaponFreezeGun : public rvWeapon {
public:
	CLASS_PROTOTYPE( rvWeaponFreezeGun );

	virtual void			Spawn( void );
	void					PreSave( void );
	void					PostSave( void );

private:
	void					UpdateBatteryGlow( void );

	stateResult_t			State_Idle( const stateParms_t &parms );
	stateResult_t			State_Fire( const stateParms_t &parms );
	stateResult_t			State_Reload( const stateParms_t &parms );

	CLASS_STATES_PROTOTYPE( rvWeaponFreezeGun );
};

CLASS_DECLARATION( rvWeapon, rvWeaponFreezeGun )
END_CLASS

CLASS_STATES_DECLARATION( rvWeaponFreezeGun )
	STATE( "Idle",		rvWeaponFreezeGun::State_Idle )
	STATE( "Fire",		rvWeaponFreezeGun::State_Fire )
	STATE( "Reload",	rvWeaponFreezeGun::State_Reload )
END_CLASS_STATES

static const int FREEZEGUN_SPARM_BATTERY = 6;
static const int FREEZEGUN_BOLTS_PER_SHOT = 5;

/*
================
rvWeaponFreezeGun::Spawn
================
*/
void rvWeaponFreezeGun::Spawn( void ) {
	SetState( "Raise", 0 );
}

/*
================
rvWeaponFreezeGun::PreSave
================
*/
void rvWeaponFreezeGun::PreSave( void ) {
	SetState( "Idle", 4 );
	StopSound( SND_CHANNEL_WEAPON, false );
	StopSound( SND_CHANNEL_BODY, false );
	StopSound( SND_CHANNEL_ITEM, false );
	StopSound( SND_CHANNEL_ANY, false );
}

/*
================
rvWeaponFreezeGun::PostSave
================
*/
void rvWeaponFreezeGun::PostSave( void ) {
}

/*
================
rvWeaponFreezeGun::UpdateBatteryGlow
================
*/
void rvWeaponFreezeGun::UpdateBatteryGlow( void ) {
	viewModel->SetShaderParm( FREEZEGUN_SPARM_BATTERY, ClipSize() ? (float)AmmoInClip() / ClipSize() : 1.0f );
}

/*
================
rvWeaponFreezeGun::State_Idle
================
*/
stateResult_t rvWeaponFreezeGun::State_Idle( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			SetStatus( AmmoAvailable() ? WP_READY : WP_OUTOFAMMO );
			UpdateBatteryGlow();
			PlayCycle( ANIMCHANNEL_ALL, "idle", parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( wsfl.lowerWeapon ) {
				SetState( "Lower", 4 );
				return SRESULT_DONE;
			}
			if ( !ClipSize() ) {
				if ( gameLocal.time > nextAttackTime && wsfl.attack && AmmoAvailable() ) {
					SetState( "Fire", 0 );
					return SRESULT_DONE;
				}
				return SRESULT_WAIT;
			}
			if ( gameLocal.time > nextAttackTime && wsfl.attack && AmmoInClip() ) {
				SetState( "Fire", 0 );
				return SRESULT_DONE;
			}
			if ( ( wsfl.attack && AutoReload() && !AmmoInClip() && AmmoAvailable() ) ||
				 wsfl.netReload ||
				 ( wsfl.reload && AmmoInClip() < ClipSize() && AmmoAvailable() > AmmoInClip() ) ) {
				SetState( "Reload", 4 );
				return SRESULT_DONE;
			}
			return SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

/*
================
rvWeaponFreezeGun::State_Fire
================
*/
stateResult_t rvWeaponFreezeGun::State_Fire( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			nextAttackTime = gameLocal.time + ( fireRate * owner->PowerUpModifier( PMOD_FIRERATE ) );
			Attack( false, FREEZEGUN_BOLTS_PER_SHOT, spread, 0, 1.0f );
			UpdateBatteryGlow();
			PlayAnim( ANIMCHANNEL_ALL, "fire", 0 );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( wsfl.attack && AmmoInClip() && !wsfl.lowerWeapon ) {
				if ( gameLocal.time >= nextAttackTime ) {
					SetState( "Fire", 0 );
					return SRESULT_DONE;
				}
				// keep the spray going rather than dropping to idle between shots
				return SRESULT_WAIT;
			}
			if ( AnimDone( ANIMCHANNEL_ALL, 0 ) ) {
				SetState( "Idle", 0 );
				return SRESULT_DONE;
			}
			return SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

/*
================
rvWeaponFreezeGun::State_Reload
================
*/
stateResult_t rvWeaponFreezeGun::State_Reload( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			if ( wsfl.netReload ) {
				wsfl.netReload = false;
			} else {
				NetReload();
			}
			viewModel->SetShaderParm( FREEZEGUN_SPARM_BATTERY, 0.0f );
			SetStatus( WP_RELOAD );
			PlayAnim( ANIMCHANNEL_ALL, "reload", parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( AnimDone( ANIMCHANNEL_ALL, 4 ) ) {
				AddToClip( ClipSize() );
				SetState( "Idle", 4 );
				return SRESULT_DONE;
			}
			if ( wsfl.lowerWeapon ) {
				SetState( "Lower", 4 );
				return SRESULT_DONE;
			}
			return SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

#include "../../Game_local.h"
#include "../../Weapon.h"

/*
===============================================================================

	WeaponSpikeGun

	A single-shot spike launcher with a scope. Unzoomed it fires the primary
	spike with an "fx_normalflash" muzzle flash; zoomed it fires the alternate
	attack. Pinning a corpse to a nearby surface is a property of the spike
	projectile's def ("canBePinned", "maxPinDistance").

===============================================================================
*/

class WeaponSpikeGun : public rvWeapon {
public:
	CLASS_PROTOTYPE( WeaponSpikeGun );

	virtual void			Spawn( void );

private:
	stateResult_t			State_Raise( const stateParms_t &parms );
	stateResult_t			State_Lower( const stateParms_t &parms );
	stateResult_t			State_Idle( const stateParms_t &parms );
	stateResult_t			State_Fire( const stateParms_t &parms );

	CLASS_STATES_PROTOTYPE( WeaponSpikeGun );
};

CLASS_DECLARATION( rvWeapon, WeaponSpikeGun )
END_CLASS

CLASS_STATES_DECLARATION( WeaponSpikeGun )
	STATE( "Raise",	WeaponSpikeGun::State_Raise )
	STATE( "Lower",	WeaponSpikeGun::State_Lower )
	STATE( "Idle",	WeaponSpikeGun::State_Idle )
	STATE( "Fire",	WeaponSpikeGun::State_Fire )
END_CLASS_STATES

/*
================
WeaponSpikeGun::Spawn
================
*/
void WeaponSpikeGun::Spawn( void ) {
	SetState( "Raise", 0 );
}

/*
================
WeaponSpikeGun::State_Raise
================
*/
stateResult_t WeaponSpikeGun::State_Raise( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			SetStatus( WP_RISING );
			PlayAnim( ANIMCHANNEL_ALL, "raise", parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( AnimDone( ANIMCHANNEL_ALL, 4 ) ) {
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

/*
================
WeaponSpikeGun::State_Lower
================
*/
stateResult_t WeaponSpikeGun::State_Lower( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT,
		STAGE_WAITRAISE
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			SetStatus( WP_LOWERING );
			PlayAnim( ANIMCHANNEL_ALL, "putaway", parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( AnimDone( ANIMCHANNEL_ALL, 0 ) ) {
				SetStatus( WP_HOLSTERED );
				return SRESULT_STAGE( STAGE_WAITRAISE );
			}
			return SRESULT_WAIT;

		case STAGE_WAITRAISE:
			if ( wsfl.raiseWeapon ) {
				SetState( "Raise", 0 );
				return SRESULT_DONE;
			}
			return SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

/*
================
WeaponSpikeGun::State_Idle
================
*/
stateResult_t WeaponSpikeGun::State_Idle( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			SetStatus( AmmoAvailable() ? WP_READY : WP_OUTOFAMMO );
			PlayCycle( ANIMCHANNEL_ALL, "idle", parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( wsfl.lowerWeapon ) {
				SetState( "Lower", 4 );
				return SRESULT_DONE;
			}
			if ( gameLocal.time > nextAttackTime && wsfl.attack && AmmoInClip() ) {
				SetState( "Fire", 0 );
				return SRESULT_DONE;
			}
			return SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

/*
================
WeaponSpikeGun::State_Fire
================
*/
stateResult_t WeaponSpikeGun::State_Fire( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			nextAttackTime = gameLocal.time + fireRate;
			if ( wsfl.zoom ) {
				Attack( true, 1, spread, 0, 1.0f );
			} else {
				Attack( false, 1, spread, 0, 1.0f );
				PlayEffect( "fx_normalflash", barrelJointView, false );
			}
			PlayAnim( ANIMCHANNEL_ALL, "fire", parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( AnimDone( ANIMCHANNEL_ALL, 0 ) ) {
				SetState( "Idle", 0 );
				return SRESULT_DONE;
			}
			return SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

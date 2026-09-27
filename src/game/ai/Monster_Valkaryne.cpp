#include "../../Game_local.h"
#include "../ScriptEvents.h"

/*
===============================================================================

	riMonsterValkaryne

	monster_q4x_valkaryne, the final boss (m09_valkaryne). The map script
	moves her between two modes with docked() and undock():

	Docked: plugged into her platform. She idles on "plugin", cannot move and
	takes no damage, and her only attack is the long "plugin_range_attack_big"
	death-ray volley (action_pluginAttackBig).

	Undocked: undock() plays "plugin_to_idle" and hands her her ranged and
	melee attacks back. She now turns only in 90 degree steps
	("turn_right_90" / "turn_left_90"), whenever the way she wants to face is
	more than three quarters of her head's look range away, or her enemy is
	out of sight on that side.

	She spawns with her ranged and melee attacks off, as the expansion's did:
	she fights only after the script has docked and undocked her. Her attacks
	themselves are frame commands in her model def.

	Her def's "requestDocking" names a script function (the map's
	valkaryne_dock) that the expansion's code parsed but never called; the
	script docks her itself, and so does nothing here.

===============================================================================
*/

class riMonsterValkaryne : public idAI {
public:
	CLASS_PROTOTYPE( riMonsterValkaryne );

							riMonsterValkaryne( void );

	void					Spawn( void );
	void					Save( idSaveGame *savefile ) const;
	void					Restore( idRestoreGame *savefile );

	virtual void			AdjustHealthByDamage( int damage );

protected:
	virtual bool			CanMove( void ) const;
	virtual const char *	GetIdleAnimName( void );
	virtual bool			CheckActions( void );

private:
	void					SetDocked( bool dock );

	rvAIAction				actionPluginAttackBig;
	bool					docked;
	bool					undockRequested;
	int						nextTurnTime;

	void					Event_Docked( void );
	void					Event_Undock( void );

	stateResult_t			State_Killed( const stateParms_t &parms );
	stateResult_t			State_Undock( const stateParms_t &parms );
	stateResult_t			State_Torso_PluginAttackBig( const stateParms_t &parms );
	stateResult_t			State_Torso_TurnRight90( const stateParms_t &parms );
	stateResult_t			State_Torso_TurnLeft90( const stateParms_t &parms );
	stateResult_t			TurnNinety( const stateParms_t &parms, const char *anim );

	CLASS_STATES_PROTOTYPE( riMonsterValkaryne );
};

CLASS_DECLARATION( idAI, riMonsterValkaryne )
	EVENT( EV_Valkaryne_Docked,	riMonsterValkaryne::Event_Docked )
	EVENT( EV_Valkaryne_Undock,	riMonsterValkaryne::Event_Undock )
END_CLASS

CLASS_STATES_DECLARATION( riMonsterValkaryne )
	STATE( "State_Killed",			riMonsterValkaryne::State_Killed )
	STATE( "Undock",				riMonsterValkaryne::State_Undock )
	STATE( "Torso_PluginAttackBig",	riMonsterValkaryne::State_Torso_PluginAttackBig )
	STATE( "Torso_TurnRight90",		riMonsterValkaryne::State_Torso_TurnRight90 )
	STATE( "Torso_TurnLeft90",		riMonsterValkaryne::State_Torso_TurnLeft90 )
END_CLASS_STATES

static const int	VALKARYNE_TURN_DELAY	= 250;
static const float	VALKARYNE_TURN_FRACTION	= 0.75f;

/*
================
riMonsterValkaryne::riMonsterValkaryne
================
*/
riMonsterValkaryne::riMonsterValkaryne( void ) {
	docked = false;
	undockRequested = false;
	nextTurnTime = 0;
}

/*
================
riMonsterValkaryne::Spawn
================
*/
void riMonsterValkaryne::Spawn( void ) {
	actionPluginAttackBig.Init( spawnArgs, "action_pluginAttackBig", "Torso_PluginAttackBig", AIACTIONF_ATTACK );

	// the plug-in attack is hers until the script undocks her
	actionPluginAttackBig.fl.disabled = false;
	actionRangedAttack.fl.disabled = true;
	actionMeleeAttack.fl.disabled = true;
}

/*
================
riMonsterValkaryne::Save
================
*/
void riMonsterValkaryne::Save( idSaveGame *savefile ) const {
	actionPluginAttackBig.Save( savefile );
	savefile->WriteBool( docked );
	savefile->WriteBool( undockRequested );
	savefile->WriteInt( nextTurnTime );
}

/*
================
riMonsterValkaryne::Restore
================
*/
void riMonsterValkaryne::Restore( idRestoreGame *savefile ) {
	actionPluginAttackBig.Restore( savefile );
	savefile->ReadBool( docked );
	savefile->ReadBool( undockRequested );
	savefile->ReadInt( nextTurnTime );
}

/*
================
riMonsterValkaryne::SetDocked
================
*/
void riMonsterValkaryne::SetDocked( bool dock ) {
	docked = dock;
	actionPluginAttackBig.fl.disabled = !dock;
	actionRangedAttack.fl.disabled = dock;
	actionMeleeAttack.fl.disabled = dock;
}

/*
================
riMonsterValkaryne::AdjustHealthByDamage
================
*/
void riMonsterValkaryne::AdjustHealthByDamage( int damage ) {
	if ( !docked ) {
		health -= damage;
	}
}

/*
================
riMonsterValkaryne::CanMove
================
*/
bool riMonsterValkaryne::CanMove( void ) const {
	return !docked && idAI::CanMove();
}

/*
================
riMonsterValkaryne::GetIdleAnimName
================
*/
const char *riMonsterValkaryne::GetIdleAnimName( void ) {
	return docked ? "plugin" : idAI::GetIdleAnimName();
}

/*
================
riMonsterValkaryne::CheckActions
================
*/
bool riMonsterValkaryne::CheckActions( void ) {
	if ( undockRequested ) {
		PerformAction( "Undock", 4, true );
		return true;
	}

	if ( docked ) {
		if ( PerformAction( &actionPluginAttackBig, (checkAction_t)&idAI::CheckAction_RangedAttack, &actionTimerSpecialAttack ) ) {
			return true;
		}
	} else if ( !move.fl.moving && gameLocal.time > nextTurnTime ) {
		// she turns in 90 degree steps, never smoothly
		const float delta = idMath::AngleNormalize180( move.ideal_yaw - move.current_yaw );
		const float limit = lookMax.yaw * VALKARYNE_TURN_FRACTION;
		if ( delta > limit || ( delta > 0.0f && !enemy.fl.inFov ) ) {
			PerformAction( "Torso_TurnRight90", 4, true );
			return true;
		}
		if ( delta < -limit || ( delta < 0.0f && !enemy.fl.inFov ) ) {
			PerformAction( "Torso_TurnLeft90", 4, true );
			return true;
		}
	}

	return idAI::CheckActions();
}

/*
================
riMonsterValkaryne::Event_Docked
================
*/
void riMonsterValkaryne::Event_Docked( void ) {
	SetDocked( true );
}

/*
================
riMonsterValkaryne::Event_Undock
================
*/
void riMonsterValkaryne::Event_Undock( void ) {
	undockRequested = true;
}

/*
================
riMonsterValkaryne::State_Killed
================
*/
stateResult_t riMonsterValkaryne::State_Killed( const stateParms_t &parms ) {
	OverrideAnim( ANIMCHANNEL_LEGS );
	PlayAnim( ANIMCHANNEL_TORSO, "death", 0 );
	PostState( "State_Dead" );
	return SRESULT_DONE;
}

/*
================
riMonsterValkaryne::State_Undock
================
*/
stateResult_t riMonsterValkaryne::State_Undock( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			PlayAnim( ANIMCHANNEL_TORSO, "plugin_to_idle", parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( AnimDone( ANIMCHANNEL_TORSO, parms.blendFrames ) ) {
				SetDocked( false );
				undockRequested = false;
				return SRESULT_DONE;
			}
			return SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

/*
================
riMonsterValkaryne::State_Torso_PluginAttackBig
================
*/
stateResult_t riMonsterValkaryne::State_Torso_PluginAttackBig( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			OverrideAnim( ANIMCHANNEL_LEGS );
			PlayAnim( ANIMCHANNEL_TORSO, "plugin_range_attack_big", parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			return AnimDone( ANIMCHANNEL_TORSO, parms.blendFrames ) ? SRESULT_DONE : SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

/*
================
riMonsterValkaryne::TurnNinety
================
*/
stateResult_t riMonsterValkaryne::TurnNinety( const stateParms_t &parms, const char *anim ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			OverrideAnim( ANIMCHANNEL_LEGS );
			PlayAnim( ANIMCHANNEL_TORSO, anim, parms.blendFrames );
			AnimTurn( 90.0f, true );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( !move.fl.moving && !AnimDone( ANIMCHANNEL_TORSO, 0 ) ) {
				return SRESULT_WAIT;
			}
			nextTurnTime = gameLocal.time + VALKARYNE_TURN_DELAY;
			AnimTurn( 0.0f, true );
			return SRESULT_DONE;
	}
	return SRESULT_ERROR;
}

/*
================
riMonsterValkaryne::State_Torso_TurnRight90
================
*/
stateResult_t riMonsterValkaryne::State_Torso_TurnRight90( const stateParms_t &parms ) {
	return TurnNinety( parms, "turn_right_90" );
}

/*
================
riMonsterValkaryne::State_Torso_TurnLeft90
================
*/
stateResult_t riMonsterValkaryne::State_Torso_TurnLeft90( const stateParms_t &parms ) {
	return TurnNinety( parms, "turn_left_90" );
}

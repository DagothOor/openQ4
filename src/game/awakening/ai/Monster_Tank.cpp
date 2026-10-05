#include "../../Game_local.h"

/*
===============================================================================

	riMonsterTank

	monster_q4x_tank: a heavy walker with three ranged attacks (railgun,
	machinegun and a shoulder rocket launcher) and two armoured parts.

	Hits in the "launcher" and "chest" damage zones wear down the part's own
	health (launcherHealth, chestHealth) and do not hurt the tank itself. A
	launcher below 85 health smokes and its rockets scatter (accuracy 10).
	Breaking either part staggers the tank and ends its rocket attack, as the
	expansion's code did.

	The breaks play "fx_chestbreak" / "fx_launcherbreak", which the def leaves
	commented out ("INSERT FX HERE"); the expansion then fell back to the
	railgun's arm explosion. The def does carry effects made for these breaks,
	"fx_chest_explode" and "fx_launcher_explode", so those come next.

===============================================================================
*/

class riMonsterTank : public idAI {
public:
	CLASS_PROTOTYPE( riMonsterTank );

							riMonsterTank( void );

	void					Spawn( void );
	void					Save( idSaveGame *savefile ) const;
	void					Restore( idRestoreGame *savefile );

	virtual int				GetDamageForLocation( int damage, int location );

protected:
	virtual bool			CheckActions( void );

private:
	void					DestroyLauncher( void );
	void					DestroyChest( void );
	void					BreakPart( const char *surface, const char *jointName, const char *effectKey, const char *authoredEffectKey );
	const char *			EffectKey( const char *preferred, const char *fallback ) const;

	rvAIAction				actionRailgunAttack;
	rvAIAction				actionMachinegunAttack;
	rvAIAction				actionRocketAttack;

	int						launcherHealth;
	int						chestHealth;
	bool					launcherSmoking;

	stateResult_t			State_Torso_RailgunAttack( const stateParms_t &parms );
	stateResult_t			State_Torso_MachinegunAttack( const stateParms_t &parms );
	stateResult_t			State_Torso_RocketAttack( const stateParms_t &parms );
	stateResult_t			PlayTorsoAttack( const stateParms_t &parms, const char *animName );

	CLASS_STATES_PROTOTYPE( riMonsterTank );
};

CLASS_DECLARATION( idAI, riMonsterTank )
END_CLASS

CLASS_STATES_DECLARATION( riMonsterTank )
	STATE( "Torso_RailgunAttack",		riMonsterTank::State_Torso_RailgunAttack )
	STATE( "Torso_MachinegunAttack",	riMonsterTank::State_Torso_MachinegunAttack )
	STATE( "Torso_RocketAttack",		riMonsterTank::State_Torso_RocketAttack )
END_CLASS_STATES

// launcher health below which it smokes and its rockets scatter
static const int TANK_LAUNCHER_SMOKE_HEALTH = 85;
static const float TANK_DAMAGED_ROCKET_ACCURACY = 10.0f;

/*
================
riMonsterTank::riMonsterTank
================
*/
riMonsterTank::riMonsterTank( void ) {
	launcherHealth = 0;
	chestHealth = 0;
	launcherSmoking = false;
}

/*
================
riMonsterTank::Spawn
================
*/
void riMonsterTank::Spawn( void ) {
	launcherHealth = spawnArgs.GetInt( "launcherHealth", "100" );
	chestHealth = spawnArgs.GetInt( "chestHealth", "100" );
	launcherSmoking = false;

	actionRailgunAttack.Init( spawnArgs, "action_railgunAttack", "Torso_RailgunAttack", AIACTIONF_ATTACK );
	actionMachinegunAttack.Init( spawnArgs, "action_machinegunAttack", "Torso_MachinegunAttack", AIACTIONF_ATTACK );
	actionRocketAttack.Init( spawnArgs, "action_rocketAttack", "Torso_RocketAttack", AIACTIONF_ATTACK );
}

/*
================
riMonsterTank::Save
================
*/
void riMonsterTank::Save( idSaveGame *savefile ) const {
	actionRailgunAttack.Save( savefile );
	actionMachinegunAttack.Save( savefile );
	actionRocketAttack.Save( savefile );
	savefile->WriteInt( launcherHealth );
	savefile->WriteInt( chestHealth );
	savefile->WriteBool( launcherSmoking );
}

/*
================
riMonsterTank::Restore
================
*/
void riMonsterTank::Restore( idRestoreGame *savefile ) {
	actionRailgunAttack.Restore( savefile );
	actionMachinegunAttack.Restore( savefile );
	actionRocketAttack.Restore( savefile );
	savefile->ReadInt( launcherHealth );
	savefile->ReadInt( chestHealth );
	savefile->ReadBool( launcherSmoking );
}

/*
================
riMonsterTank::CheckActions
================
*/
bool riMonsterTank::CheckActions( void ) {
	if ( CheckPainActions() ) {
		return true;
	}
	if ( PerformAction( &actionRailgunAttack, (checkAction_t)&idAI::CheckAction_RangedAttack, &actionTimerRangedAttack ) ||
		 PerformAction( &actionMachinegunAttack, (checkAction_t)&idAI::CheckAction_RangedAttack, &actionTimerSpecialAttack ) ) {
		return true;
	}
	if ( launcherHealth > 0 && PerformAction( &actionRocketAttack, (checkAction_t)&idAI::CheckAction_RangedAttack, &actionTimerRangedAttack ) ) {
		return true;
	}
	return idAI::CheckActions();
}

/*
================
riMonsterTank::GetDamageForLocation

The launcher and chest take hits in the tank's place.
================
*/
int riMonsterTank::GetDamageForLocation( int damage, int location ) {
	const char *group = GetDamageGroup( location );

	if ( idStr::Icmp( group, "launcher" ) == 0 ) {
		if ( launcherHealth > 0 ) {
			launcherHealth -= damage;
			if ( launcherHealth <= 0 ) {
				DestroyLauncher();
			} else if ( launcherHealth < TANK_LAUNCHER_SMOKE_HEALTH && !launcherSmoking ) {
				PlayEffect( EffectKey( "fx_launchersmoke", "fx_railgun_burn" ), animator.GetJointHandle( "launcher_break" ), true );
				spawnArgs.SetFloat( "attack_rocket_accuracy", TANK_DAMAGED_ROCKET_ACCURACY );
				launcherSmoking = true;
			}
		}
		return 0;
	}

	if ( idStr::Icmp( group, "chest" ) == 0 ) {
		if ( chestHealth > 0 ) {
			chestHealth -= damage;
			if ( chestHealth <= 0 ) {
				DestroyChest();
			}
		}
		return 0;
	}

	return idAI::GetDamageForLocation( damage, location );
}

/*
================
riMonsterTank::EffectKey

The part effects are optional def keys with a stock fallback key.
================
*/
const char *riMonsterTank::EffectKey( const char *preferred, const char *fallback ) const {
	return spawnArgs.FindKey( preferred ) ? preferred : fallback;
}

/*
================
riMonsterTank::BreakPart
================
*/
void riMonsterTank::BreakPart( const char *surface, const char *jointName, const char *effectKey, const char *authoredEffectKey ) {
	if ( DebugActions() ) {
		gameLocal.Printf( "%d %s: breaks %s\n", gameLocal.time, name.c_str(), jointName );
	}
	HideSurface( surface );

	idVec3 origin;
	idMat3 axis;
	GetJointWorldTransform( animator.GetJointHandle( jointName ), gameLocal.time, origin, axis );
	gameLocal.PlayEffect( gameLocal.GetEffect( spawnArgs, EffectKey( effectKey, EffectKey( authoredEffectKey, "fx_railgun_explode" ) ) ), origin, axis );

	// the break staggers the tank and silences its launcher
	pain.takenThisFrame = pain.threshold;
	pain.lastTakenTime = gameLocal.time;
	actionRocketAttack.fl.disabled = true;
}

/*
================
riMonsterTank::DestroyLauncher
================
*/
void riMonsterTank::DestroyLauncher( void ) {
	launcherHealth = -1;
	StopEffect( EffectKey( "fx_launchersmoke", "fx_railgun_burn" ) );
	BreakPart( "models/monsters/tank/tank_launcherbreak", "launcher_break", "fx_launcherbreak", "fx_launcher_explode" );
}

/*
================
riMonsterTank::DestroyChest
================
*/
void riMonsterTank::DestroyChest( void ) {
	chestHealth = -1;
	HideSurface( "models/monsters/tank/tank_skull" );
	BreakPart( "models/monsters/tank/tank_chestbreak", "chestbreak", "fx_chestbreak", "fx_chest_explode" );
}

/*
================
riMonsterTank::PlayTorsoAttack
================
*/
stateResult_t riMonsterTank::PlayTorsoAttack( const stateParms_t &parms, const char *animName ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			OverrideAnim( ANIMCHANNEL_LEGS );
			PlayAnim( ANIMCHANNEL_TORSO, animName, parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			if ( AnimDone( ANIMCHANNEL_TORSO, parms.blendFrames ) ) {
				return SRESULT_DONE;
			}
			return SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

/*
================
riMonsterTank::State_Torso_RailgunAttack
================
*/
stateResult_t riMonsterTank::State_Torso_RailgunAttack( const stateParms_t &parms ) {
	return PlayTorsoAttack( parms, "railgun_attack" );
}

/*
================
riMonsterTank::State_Torso_MachinegunAttack
================
*/
stateResult_t riMonsterTank::State_Torso_MachinegunAttack( const stateParms_t &parms ) {
	return PlayTorsoAttack( parms, "machinegun_attack" );
}

/*
================
riMonsterTank::State_Torso_RocketAttack
================
*/
stateResult_t riMonsterTank::State_Torso_RocketAttack( const stateParms_t &parms ) {
	return PlayTorsoAttack( parms, "rocket_attack" );
}

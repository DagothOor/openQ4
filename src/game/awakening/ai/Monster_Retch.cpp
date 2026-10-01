#include "../../Game_local.h"
#include "../../ai/AI_Manager.h"

/*
===============================================================================

	riMonsterRetch

	monster_q4x_retch: a Strogg support unit that buffs its allies.

	When it has no buff running it looks for another AI on its team that is not
	itself a retch and not already buffed, and picks one of two buffs at random:
	a defense buff (the ally takes defenseBoostMult of the damage it would) or
	a damage buff (the ally deals damageBoostMult). The ally and the retch get
	a matching overlay, and the retch plays its "buff" animation while a beam
	(fx_buffBeam) runs from its DM_muzzle1 joint to the ally. The buff lasts
	until either of them dies.

	It also strafes (action_strafe) while it has a clear shot.

===============================================================================
*/

class riMonsterRetch : public idAI {
public:
	CLASS_PROTOTYPE( riMonsterRetch );

							riMonsterRetch( void );

	void					Spawn( void );
	void					Save( idSaveGame *savefile ) const;
	void					Restore( idRestoreGame *savefile );

protected:
	virtual bool			CheckActions( void );
	virtual void			OnDeath( void );

private:
	bool					FindBuffTarget( void );
	void					ApplyBuff( idAI *ally );
	void					ClearBuff( void );
	void					UpdateBuffBeam( void );
	void					StopBuffBeam( void );

	bool					CheckAction_Strafe( rvAIAction *action, int animNum );

	rvAIAction				actionStrafe;

	idEntityPtr<idAI>		buffTarget;
	bool					defenseBuff;
	rvClientEntityPtr<rvClientEffect>	buffBeam;

	stateResult_t			State_Buff( const stateParms_t &parms );

	CLASS_STATES_PROTOTYPE( riMonsterRetch );
};

CLASS_DECLARATION( idAI, riMonsterRetch )
END_CLASS

CLASS_STATES_DECLARATION( riMonsterRetch )
	STATE( "Buff",	riMonsterRetch::State_Buff )
END_CLASS_STATES

static const char * const RETCH_DEFENSE_OVERLAY = "common/defense_boost_overlay";
static const char * const RETCH_DAMAGE_OVERLAY = "common/damage_boost_overlay";
static const float RETCH_BEAM_RANGE = 4096.0f;

/*
================
riMonsterRetch::riMonsterRetch
================
*/
riMonsterRetch::riMonsterRetch( void ) {
	defenseBuff = false;
}

/*
================
riMonsterRetch::Spawn
================
*/
void riMonsterRetch::Spawn( void ) {
	actionStrafe.Init( spawnArgs, "action_strafe", NULL, 0 );
	buffTarget = NULL;
}

/*
================
riMonsterRetch::Save
================
*/
void riMonsterRetch::Save( idSaveGame *savefile ) const {
	actionStrafe.Save( savefile );
	buffTarget.Save( savefile );
	savefile->WriteBool( defenseBuff );
}

/*
================
riMonsterRetch::Restore

Damage scales and overlays are not saved with the ally; put them back.
================
*/
void riMonsterRetch::Restore( idRestoreGame *savefile ) {
	actionStrafe.Restore( savefile );
	buffTarget.Restore( savefile );
	savefile->ReadBool( defenseBuff );

	if ( buffTarget.GetEntity() != NULL ) {
		ApplyBuff( buffTarget.GetEntity() );
	}
}

/*
================
riMonsterRetch::ApplyBuff
================
*/
void riMonsterRetch::ApplyBuff( idAI *ally ) {
	const idMaterial *overlay;
	if ( defenseBuff ) {
		ally->SetDamageScales( ally->GetDamageDealtScale(), spawnArgs.GetFloat( "defenseBoostMult", "0" ) );
		overlay = declManager->FindMaterial( RETCH_DEFENSE_OVERLAY );
		ally->PlayEffect( "fx_defenseBoost", ally->GetAnimator()->GetJointHandle( "origin" ), true );
		PlayEffect( "fx_defenseBoost", animator.GetJointHandle( "origin" ), true );
	} else {
		ally->SetDamageScales( spawnArgs.GetFloat( "damageBoostMult", "0" ), ally->GetDamageTakenScale() );
		overlay = declManager->FindMaterial( RETCH_DAMAGE_OVERLAY );
		ally->PlayEffect( "fx_damageBoost", ally->GetAnimator()->GetJointHandle( "origin" ), true );
		PlayEffect( "fx_damageBoost", animator.GetJointHandle( "origin" ), true );
	}
	ally->GetRenderEntity()->overlayShader = overlay;
	ally->UpdateVisuals();
	renderEntity.overlayShader = overlay;
	UpdateVisuals();
}

/*
================
riMonsterRetch::ClearBuff
================
*/
void riMonsterRetch::ClearBuff( void ) {
	idAI *ally = buffTarget.GetEntity();
	const char *effect = defenseBuff ? "fx_defenseBoost" : "fx_damageBoost";
	if ( ally != NULL ) {
		ally->SetDamageScales( 1.0f, 1.0f );
		ally->GetRenderEntity()->overlayShader = NULL;
		ally->StopEffect( effect );
		ally->UpdateVisuals();
	}
	StopEffect( effect );
	renderEntity.overlayShader = NULL;
	UpdateVisuals();
	buffTarget = NULL;
	StopBuffBeam();
}

/*
================
riMonsterRetch::FindBuffTarget
================
*/
bool riMonsterRetch::FindBuffTarget( void ) {
	for ( idActor *actor = aiManager.GetAllyTeam( (aiTeam_t)team ); actor != NULL; actor = actor->teamNode.Next() ) {
		if ( actor == this || !actor->IsType( idAI::GetClassType() ) || actor->IsType( riMonsterRetch::GetClassType() ) ) {
			continue;
		}
		idAI *ally = static_cast<idAI *>( actor );
		// an overlay means another retch (or a powerup) already has it
		if ( ally->aifl.dead || ally->GetRenderEntity()->overlayShader != NULL ) {
			continue;
		}

		defenseBuff = ( gameLocal.random.RandomInt( 2 ) == 0 );
		buffTarget = ally;
		ApplyBuff( ally );
		TurnToward( ally->GetPhysics()->GetOrigin() );
		return true;
	}
	return false;
}

/*
================
riMonsterRetch::UpdateBuffBeam

Runs the beam from the retch's muzzle to the middle of its ally.
================
*/
void riMonsterRetch::UpdateBuffBeam( void ) {
	idAI *ally = buffTarget.GetEntity();
	if ( ally == NULL ) {
		StopBuffBeam();
		return;
	}

	idVec3 start;
	idMat3 axis;
	GetJointWorldTransform( animator.GetJointHandle( "DM_muzzle1" ), gameLocal.time, start, axis );

	idVec3 dir = ally->GetPhysics()->GetAbsBounds().GetCenter() - start;
	dir.Normalize();
	trace_t tr;
	gameLocal.TracePoint( this, tr, start, start + dir * RETCH_BEAM_RANGE, MASK_SHOT_RENDERMODEL, this );

	rvClientEffect *beam = buffBeam.GetEntity();
	if ( beam != NULL ) {
		beam->SetOrigin( start );
		beam->SetAxis( dir.ToMat3() );
		beam->SetEndOrigin( tr.endpos );
		return;
	}
	buffBeam = PlayEffect( "fx_buffBeam", start, dir.ToMat3(), true, tr.endpos );
}

/*
================
riMonsterRetch::StopBuffBeam
================
*/
void riMonsterRetch::StopBuffBeam( void ) {
	rvClientEffect *beam = buffBeam.GetEntity();
	if ( beam != NULL ) {
		beam->Stop();
	}
	buffBeam = NULL;
}

/*
================
riMonsterRetch::CheckAction_Strafe
================
*/
bool riMonsterRetch::CheckAction_Strafe( rvAIAction *action, int animNum ) {
	if ( !enemy.fl.visible || !enemy.fl.inFov || !move.fl.done ) {
		return false;
	}
	return animNum == -1 || TestAnimMove( animNum );
}

/*
================
riMonsterRetch::CheckActions
================
*/
bool riMonsterRetch::CheckActions( void ) {
	idAI *ally = buffTarget.GetEntity();

	if ( ally == NULL && FindBuffTarget() ) {
		PerformAction( "Buff", 2, true );
		return true;
	}

	// the buff ends when the ally dies
	if ( ally != NULL && ally->aifl.dead ) {
		ClearBuff();
	}

	if ( PerformAction( &actionStrafe, (checkAction_t)&riMonsterRetch::CheckAction_Strafe ) ) {
		return true;
	}
	return idAI::CheckActions();
}

/*
================
riMonsterRetch::OnDeath
================
*/
void riMonsterRetch::OnDeath( void ) {
	ClearBuff();
	idAI::OnDeath();
}

/*
================
riMonsterRetch::State_Buff
================
*/
stateResult_t riMonsterRetch::State_Buff( const stateParms_t &parms ) {
	enum {
		STAGE_INIT,
		STAGE_WAIT
	};
	switch ( parms.stage ) {
		case STAGE_INIT:
			OverrideAnim( ANIMCHANNEL_LEGS );
			PlayAnim( ANIMCHANNEL_TORSO, "buff", parms.blendFrames );
			return SRESULT_STAGE( STAGE_WAIT );

		case STAGE_WAIT:
			UpdateBuffBeam();
			if ( AnimDone( ANIMCHANNEL_TORSO, parms.blendFrames ) ) {
				StopBuffBeam();
				return SRESULT_DONE;
			}
			return SRESULT_WAIT;
	}
	return SRESULT_ERROR;
}

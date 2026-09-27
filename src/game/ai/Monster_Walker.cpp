#include "../../Game_local.h"

/*
===============================================================================

	riMonsterWalker

	monster_q4x_walker: the Strogg walker mech fought on foot. It is a plain
	idAI driven by its def's actions; only its death differs. A walker has no
	ragdoll, so it plays its "death" animation on the torso with the legs
	following, then settles in State_Dead.

===============================================================================
*/

class riMonsterWalker : public idAI {
public:
	CLASS_PROTOTYPE( riMonsterWalker );

private:
	stateResult_t			State_Killed( const stateParms_t &parms );

	CLASS_STATES_PROTOTYPE( riMonsterWalker );
};

CLASS_DECLARATION( idAI, riMonsterWalker )
END_CLASS

CLASS_STATES_DECLARATION( riMonsterWalker )
	STATE( "State_Killed",	riMonsterWalker::State_Killed )
END_CLASS_STATES

/*
================
riMonsterWalker::State_Killed
================
*/
stateResult_t riMonsterWalker::State_Killed( const stateParms_t &parms ) {
	DisableAnimState( ANIMCHANNEL_TORSO );
	DisableAnimState( ANIMCHANNEL_LEGS );
	OverrideAnim( ANIMCHANNEL_LEGS );
	PlayAnim( ANIMCHANNEL_TORSO, "death", parms.blendFrames );
	PostState( "State_Dead" );
	return SRESULT_DONE;
}

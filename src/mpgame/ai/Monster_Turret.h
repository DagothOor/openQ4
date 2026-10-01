#ifndef __GAME_MONSTER_TURRET_H__
#define __GAME_MONSTER_TURRET_H__

/*
===============================================================================

	rvMonsterTurret

	Declared here so game-library layers can build on it: the Awakening
	expansion's turrets add tracking, accuracy and scanning behaviour.

===============================================================================
*/

class rvMonsterTurret : public idAI {
public:

	CLASS_PROTOTYPE( rvMonsterTurret );

	rvMonsterTurret ( void );

	void				InitSpawnArgsVariables	( void );
	void				Spawn					( void );
	void				Save					( idSaveGame *savefile ) const;
	void				Restore					( idRestoreGame *savefile );

	virtual bool		Pain					( idEntity *inflictor, idEntity *attacker, int damage, const idVec3 &dir, int location );

protected:

	virtual bool		CheckActions			( void );

	stateResult_t		State_Combat			( const stateParms_t& parms );
	stateResult_t		State_Killed			( const stateParms_t& parms );

	int					shieldHealth;
	int					maxShots;	
	int					minShots;
	int					shots;

	rvAIAction			actionBlasterAttack;

	stateResult_t		State_Torso_BlasterAttack	( const stateParms_t& parms );

	CLASS_STATES_PROTOTYPE ( rvMonsterTurret );
};

#endif /* !__GAME_MONSTER_TURRET_H__ */

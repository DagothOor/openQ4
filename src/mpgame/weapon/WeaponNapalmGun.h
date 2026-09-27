#ifndef __GAME_WEAPONNAPALMGUN_H__
#define __GAME_WEAPONNAPALMGUN_H__

/*
===============================================================================

	WeaponNapalmGun

	Declared here so game-library layers can build on it: the Awakening
	expansion names the same weapon WeaponGoobGun.

===============================================================================
*/

const int NAPALM_GUN_NUM_CYLINDERS =  5;

class WeaponNapalmGun : public rvWeapon {
public:

	CLASS_PROTOTYPE( WeaponNapalmGun );

	WeaponNapalmGun ( void );
	~WeaponNapalmGun ( void );

	virtual void			Spawn				( void );
	virtual void			Think				( void );
	virtual void			MuzzleRise			( idVec3 &origin, idMat3 &axis );

	virtual void			SpectatorCycle		( void );

	void					Save( idSaveGame *saveFile ) const;
	void					Restore( idRestoreGame *saveFile );

protected:

	void					UpdateCylinders(void);
	
	typedef enum {CYLINDER_RESET_POSITION,CYLINDER_MOVE_POSITION, CYLINDER_UPDATE_POSITION } CylinderState;
	CylinderState								cylinderState;

protected:

	stateResult_t		State_Idle				( const stateParms_t& parms );
	stateResult_t		State_Fire				( const stateParms_t& parms );
	stateResult_t		State_Reload			( const stateParms_t& parms );
	stateResult_t		State_EmptyReload		( const stateParms_t& parms );
	
	stateResult_t		Frame_MoveCylinder		( const stateParms_t& parms );
	stateResult_t		Frame_ResetCylinder		( const stateParms_t& parms );


	float								cylinderMaxOffsets[NAPALM_GUN_NUM_CYLINDERS];
	idInterpolate<float>				cylinderOffsets[NAPALM_GUN_NUM_CYLINDERS];
	jointHandle_t						cylinderJoints[NAPALM_GUN_NUM_CYLINDERS];


	int									cylinderMoveTime;
	int									previousAmmo;
	bool								zoomed;
	
	CLASS_STATES_PROTOTYPE ( WeaponNapalmGun );
};

#endif /* !__GAME_WEAPONNAPALMGUN_H__ */

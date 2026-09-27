#ifndef __AWAKENING_SPACEROCKET_H__
#define __AWAKENING_SPACEROCKET_H__

#include "../Projectile.h"

/*
===============================================================================

	riProjectileSpaceRocket

	The rocket of the Awakening's turret missile launchers. Given a target it
	homes: each frame it swings its velocity towards the target's middle
	(plus the def's "projectileTargetOffset"), turning harder as it ages, from
	5% of the way at launch to 25% after a second. Given only a point, it
	homes on that point as seen from where it is, so a miss keeps flying.
	Without either it is an ordinary projectile.

===============================================================================
*/

class riProjectileSpaceRocket : public idProjectile {
public:
	CLASS_PROTOTYPE( riProjectileSpaceRocket );

							riProjectileSpaceRocket( void );

	void					Save( idSaveGame *savefile ) const;
	void					Restore( idRestoreGame *savefile );

	virtual void			Think( void );

	void					SetTarget( idEntity *ent );
	void					SetTargetPosition( const idVec3 &position );
							// bends the flight direction by a unit-length-scaled offset (a spread pattern)
	void					BendDirection( const idVec3 &offset );

private:
	int						homingStartTime;
	idEntityPtr<idEntity>	target;
	idVec3					targetOffset;
	idVec3					targetPosition;
	bool					hasTargetPosition;
};

#endif /* !__AWAKENING_SPACEROCKET_H__ */

#include "../Game_local.h"
#include "SpaceRocket.h"

CLASS_DECLARATION( idProjectile, riProjectileSpaceRocket )
END_CLASS

static const float SPACEROCKET_TURN_MIN			= 0.05f;
static const float SPACEROCKET_TURN_GAIN		= 0.2f;
static const float SPACEROCKET_POINT_LOOKAHEAD	= 10000.0f;

/*
================
riProjectileSpaceRocket::riProjectileSpaceRocket
================
*/
riProjectileSpaceRocket::riProjectileSpaceRocket( void ) {
	homingStartTime = 0;
	targetOffset.Zero();
	targetPosition.Zero();
	hasTargetPosition = false;
}

/*
================
riProjectileSpaceRocket::Save
================
*/
void riProjectileSpaceRocket::Save( idSaveGame *savefile ) const {
	savefile->WriteInt( homingStartTime );
	target.Save( savefile );
	savefile->WriteVec3( targetOffset );
	savefile->WriteVec3( targetPosition );
	savefile->WriteBool( hasTargetPosition );
}

/*
================
riProjectileSpaceRocket::Restore
================
*/
void riProjectileSpaceRocket::Restore( idRestoreGame *savefile ) {
	savefile->ReadInt( homingStartTime );
	target.Restore( savefile );
	savefile->ReadVec3( targetOffset );
	savefile->ReadVec3( targetPosition );
	savefile->ReadBool( hasTargetPosition );
}

/*
================
riProjectileSpaceRocket::SetTarget
================
*/
void riProjectileSpaceRocket::SetTarget( idEntity *ent ) {
	target = ent;
	targetOffset = spawnArgs.GetVector( "projectileTargetOffset", "0 0 0" );
	homingStartTime = gameLocal.time;
}

/*
================
riProjectileSpaceRocket::SetTargetPosition
================
*/
void riProjectileSpaceRocket::SetTargetPosition( const idVec3 &position ) {
	targetPosition = position;
	hasTargetPosition = true;
	homingStartTime = gameLocal.time;
}

/*
================
riProjectileSpaceRocket::BendDirection
================
*/
void riProjectileSpaceRocket::BendDirection( const idVec3 &offset ) {
	idVec3 velocity = physicsObj.GetLinearVelocity();
	const float speed = velocity.Normalize();
	if ( speed <= 0.0f ) {
		return;
	}
	velocity += offset;
	velocity.Normalize();
	physicsObj.SetLinearVelocity( velocity * speed );
}

/*
================
riProjectileSpaceRocket::Think
================
*/
void riProjectileSpaceRocket::Think( void ) {
	idEntity *ent = target.GetEntity();
	bool homing = false;
	idVec3 aim;
	const idVec3 &origin = physicsObj.GetOrigin();

	if ( ent != NULL && ent->health > 0 ) {
		aim = ent->GetPhysics()->GetAbsBounds().GetCenter() + targetOffset;
		homing = true;
	} else if ( hasTargetPosition ) {
		// keep the point ahead of us, so passing it does not turn us around
		idVec3 toPoint = targetPosition - origin;
		if ( toPoint.Normalize() > 0.0f ) {
			targetPosition = origin + toPoint * SPACEROCKET_POINT_LOOKAHEAD;
		}
		aim = targetPosition;
		homing = true;
	}

	if ( homing ) {
		idVec3 velocity = physicsObj.GetLinearVelocity();
		const float speed = velocity.Normalize();
		idVec3 toAim = aim - origin;
		if ( speed > 0.0f && toAim.Normalize() > 0.0f ) {
			const float age = idMath::ClampFloat( 0.0f, 1.0f, MS2SEC( gameLocal.time - homingStartTime ) );
			const float turn = SPACEROCKET_TURN_MIN + SPACEROCKET_TURN_GAIN * age;
			idVec3 dir = toAim * turn + velocity * ( 1.0f - turn );
			if ( dir.Normalize() > 0.0f ) {
				physicsObj.SetLinearVelocity( dir * speed );
			}
		}
	}

	idProjectile::Think();
}

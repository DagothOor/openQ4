#include "../../Game_local.h"
#include "../../Weapon.h"
#include "../../weapon/WeaponNapalmGun.h"

/*
===============================================================================

	WeaponGoobGun

	The expansion's Goob Gun is openQ4's napalm gun under the name the
	expansion's weapon defs use (weaponclass "WeaponGoobGun"): the same
	five-cylinder launcher with the same states. What sets it apart lives in its
	defs, whose projectiles leave burning goo (impactEntity) and whose damage
	sets targets alight through the FireDOTEntity their damage defs spawn.

===============================================================================
*/

class WeaponGoobGun : public WeaponNapalmGun {
public:
	CLASS_PROTOTYPE( WeaponGoobGun );
};

CLASS_DECLARATION( WeaponNapalmGun, WeaponGoobGun )
END_CLASS

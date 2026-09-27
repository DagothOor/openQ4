#include "../Game_local.h"

/*
===============================================================================

	The Awakening's buy-menu prices

	The expansion kept its multiplayer prices in code rather than in an
	ItemCostConstants def, so this layer registers them (idBuyItemPrice). They
	come before the retail prices its content still carries, and pricing the
	weapon mods and FC Armor Regen is what puts them on sale. A weapon mod sells
	only to a player carrying its weapon; the team specials (ammo_regen,
	health_regen, damage_boost, fc_armor_regen) only in team games.

	The core cannon and fire cannon on the buy menu are the spike gun and the
	goob gun.

===============================================================================
*/

// weapons
BUY_ITEM_PRICE( weapon_shotgun,						500 )
BUY_ITEM_PRICE( weapon_hyperblaster,				700 )
BUY_ITEM_PRICE( weapon_nailgun,						900 )
BUY_ITEM_PRICE( weapon_grenadelauncher,				1000 )
BUY_ITEM_PRICE( weapon_goobgun,						1300 )
BUY_ITEM_PRICE( weapon_spikegun,					1300 )
BUY_ITEM_PRICE( weapon_lightninggun,				1500 )
BUY_ITEM_PRICE( weapon_rocketlauncher,				2000 )
BUY_ITEM_PRICE( weapon_railgun,						3000 )
BUY_ITEM_PRICE( weapon_dmg,							5000 )
BUY_ITEM_PRICE( weapon_freezegun,					500 )

// weapon mods
BUY_ITEM_PRICE( wpmod_shotgun_ammo,					2000 )
BUY_ITEM_PRICE( wpmod_railgun_penetrate,			2500 )
BUY_ITEM_PRICE( wpmod_grenade_concussion_blast,		7000 )
BUY_ITEM_PRICE( wpmod_nailgun_rof,					5000 )
BUY_ITEM_PRICE( wpmod_lightninggun_chain,			6000 )
BUY_ITEM_PRICE( wpmod_hyperblaster_bounce1,			8000 )
BUY_ITEM_PRICE( wpmod_rocketlauncher_burst,			12000 )
BUY_ITEM_PRICE( wpmod_spikegun_scope,				1800 )
BUY_ITEM_PRICE( wpmod_goobgun_flamethrower,			6500 )

// armor and ammo
BUY_ITEM_PRICE( item_armor_small,					300 )
BUY_ITEM_PRICE( item_armor_large,					700 )
BUY_ITEM_PRICE( ammorefill,							500 )

// team specials
BUY_ITEM_PRICE( ammo_regen,							10000 )
BUY_ITEM_PRICE( health_regen,						12500 )
BUY_ITEM_PRICE( damage_boost,						15000 )
BUY_ITEM_PRICE( fc_armor_regen,						3000 )

#include "../Game_local.h"

#include "ObjectiveBeacon.h"

/*
===============================================================================

	idTarget_ObjectiveBeacon

	target_objectivebeacon marks where an objective physically is. Activating a
	beacon makes it the current one, the anchor for the objective compass. The
	expansion's HUD compass was never finished (its q4xhud.gui windows are
	commented out and the shipped game code never read the beacon), so this
	records the beacon for a compass to use and changes nothing on screen.

===============================================================================
*/

CLASS_DECLARATION( idTarget, idTarget_ObjectiveBeacon )
	EVENT( EV_Activate,		idTarget_ObjectiveBeacon::Event_Activate )
END_CLASS

idEntityPtr<idEntity> idTarget_ObjectiveBeacon::current;

/*
================
idTarget_ObjectiveBeacon::GetCurrent
================
*/
idTarget_ObjectiveBeacon *idTarget_ObjectiveBeacon::GetCurrent( void ) {
	idEntity *ent = current.GetEntity();
	if ( ent == NULL || !ent->IsType( idTarget_ObjectiveBeacon::GetClassType() ) ) {
		return NULL;
	}
	return static_cast<idTarget_ObjectiveBeacon *>( ent );
}

/*
================
idTarget_ObjectiveBeacon::Event_Activate
================
*/
void idTarget_ObjectiveBeacon::Event_Activate( idEntity *activator ) {
	current = this;
	if ( g_debugTriggers.GetBool() ) {
		gameLocal.Printf( "%d: objective beacon '%s' is now current\n", gameLocal.framenum, GetName() );
	}
}

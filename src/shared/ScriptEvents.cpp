#include "../Game_local.h"

#include "ScriptEvents.h"

const idEventDef EV_SpeederBike_SetSpeed( "setSpeederBikeSpeed", "ff" );
const idEventDef EV_SpeederBike_SetMaxGravityDistance( "setSpeederBikeMaxGravityDistance", "ff" );
const idEventDef EV_SpeederBike_SetBoostEnabled( "setSpeederBikeBoostEnabled", "f" );

const idEventDef EV_Valkaryne_Docked( "docked" );
const idEventDef EV_Valkaryne_Undock( "undock" );

const idEventDef EV_PainLord_RequestProcessing( "requestProcessing" );
const idEventDef EV_PainLord_AtProcessingStation( "atProcessingStation" );

const idEventDef EV_Thread_ControlPointController( "controlPointController", NULL, 'd' );
const idEventDef EV_Thread_ControlPercentToWin( "controlPercentToWin", NULL, 'f' );

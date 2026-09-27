#ifndef __AWAKENING_OBJECTIVEBEACON_H__
#define __AWAKENING_OBJECTIVEBEACON_H__

/*
===============================================================================

	idTarget_ObjectiveBeacon

	Marks the physical location of an objective; the most recently activated
	beacon is the current one.

===============================================================================
*/

class idTarget_ObjectiveBeacon : public idTarget {
public:
	CLASS_PROTOTYPE( idTarget_ObjectiveBeacon );

	static idTarget_ObjectiveBeacon *	GetCurrent( void );

private:
	void								Event_Activate( idEntity *activator );

	// an idEntity pointer, type-checked on read, because it outlives the map
	static idEntityPtr<idEntity>		current;
};

#endif /* !__AWAKENING_OBJECTIVEBEACON_H__ */

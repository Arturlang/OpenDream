#ifdef OPENDREAM
#define ENGINE "od"
#else
#define ENGINE "byond"
#endif

/world
	view = 7
	maxx = 60
	maxy = 15
	maxz = 1
	fps = 20
	turf = /turf/floor
	mob = /mob/walker

/turf/floor
	icon = 'tiles.dmi'
	icon_state = "floor"

/mob/walker
	icon = 'tiles.dmi'
	icon_state = "white"

var/list/events = list()
var/list/held = list()

/proc/note(text)
	events += "[world.time]\t[text]"
	text2file("[world.time]\t[text]", "events_[ENGINE].txt")

/client/verb/keyDown(_key as text)
	set instant = TRUE
	set hidden = TRUE
	held[_key] = TRUE
	note("down [_key]")

/client/verb/keyUp(_key as text)
	set instant = TRUE
	set hidden = TRUE
	held -= _key
	note("up [_key]")

/mob/walker/Login()
	..()
	loc = locate(5, 8, 1)
	fdel("events_[ENGINE].txt")
	spawn(0)
		while(client)
			if(held["D"])
				step(src, EAST)
				note("moved to x=[x]")
			sleep(world.tick_lag)

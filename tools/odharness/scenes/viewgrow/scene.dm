// Does a screen object grow the map? -D BIG puts a 64x64 icon at EAST,NORTH (overhangs the view).
// -D PLACED puts a 32x32 icon at EAST+1,NORTH (placed outside the view). Neither: plain 7x7 view.

/world
	view = 3
	maxx = 20
	maxy = 20
	maxz = 1
	turf = /turf/floor
	mob = /mob/viewer
	icon_size = 32

/turf/floor
	icon = 'tiles.dmi'
	icon_state = "floor"

/obj/hud
	plane = 100

/mob/viewer
	invisibility = 101

/mob/viewer/Login()
	..()
	loc = locate(10, 10, 1)
	var/obj/hud/H = new
#ifdef BIG
	H.icon = 'big.dmi'
	H.icon_state = "big"
	H.screen_loc = "EAST,NORTH"
#elif defined(PLACED)
	H.icon = 'tiles.dmi'
	H.icon_state = "dot"
	H.screen_loc = "EAST+1,NORTH"
#else
	H.icon = 'tiles.dmi'
	H.icon_state = "dot"
	H.screen_loc = "EAST,NORTH"
#endif
	client.screen += H

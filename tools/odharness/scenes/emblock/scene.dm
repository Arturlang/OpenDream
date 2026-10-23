// TGMC human with a helmet: KEEP_TOGETHER mob, emissive blockers (black copies on plane 13, which a plane master
// renders to a hidden target), one on the mob and one nested inside the worn helmet overlay
#define EMISSIVE_PLANE 13
#define EMISSIVE_APPEARANCE_FLAGS (KEEP_APART|KEEP_TOGETHER|RESET_COLOR|RESET_TRANSFORM)

/world
	view = 3
	maxx = 7
	maxy = 7
	maxz = 1
	turf = /turf/floor
	mob = /mob/human

/turf/floor
	icon = 'tiles.dmi'
	icon_state = "floor"

/obj/emissive_master
	appearance_flags = PLANE_MASTER
	plane = EMISSIVE_PLANE
	screen_loc = "1,1"
	render_target = "*EMISSIVE_RENDER_TARGET"

/mob/human
	icon = 'ghost.dmi'
	icon_state = "ghost"
	dir = EAST
	appearance_flags = KEEP_TOGETHER|TILE_BOUND|PIXEL_SCALE|LONG_GLIDE

/proc/blocker(icon, state, dir)
	var/mutable_appearance/B = new()
	B.icon = icon
	B.icon_state = state
	B.dir = dir
	B.appearance_flags = EMISSIVE_APPEARANCE_FLAGS
	B.color = "#000000"
	B.plane = EMISSIVE_PLANE
	return B

/mob/human/Login()
	..()
	loc = locate(4, 4, 1)
	client.screen += new /obj/emissive_master
#ifndef NO_BODY_BLOCKER
	overlays += blocker(icon, icon_state, dir)
#endif
	var/mutable_appearance/helmet = new()
	helmet.icon = 'helm.dmi'
	helmet.icon_state = "helm"
	helmet.plane = FLOAT_PLANE
	helmet.layer = FLOAT_LAYER
#ifndef NO_HELMET_BLOCKER
	helmet.overlays += blocker('helm.dmi', "helm", dir)
#endif
	overlays += helmet

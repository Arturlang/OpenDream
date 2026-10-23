// TGMC's hair under a helmet: a KEEP_TOGETHER mob whose hair overlay carries a mask image that renders to a
// hidden "*" target, and an alpha mask filter on the hair reading that target. The mask must never be drawn.
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

/mob/human
	icon = 'ghost.dmi'
	icon_state = "ghost"
#ifdef NO_KT
	appearance_flags = TILE_BOUND|PIXEL_SCALE|LONG_GLIDE
#else
	appearance_flags = KEEP_TOGETHER|TILE_BOUND|PIXEL_SCALE|LONG_GLIDE
#endif

/mob/human/Login()
	..()
	loc = locate(4, 4, 1)
	dir = WEST
	var/mutable_appearance/hair = new()
	hair.icon = 'ghost.dmi'
	hair.icon_state = "ghost_red"
	hair.plane = FLOAT_PLANE
	hair.layer = FLOAT_LAYER
	var/image/mask = image('human_face.dmi', null, "Jeager_Mask")
	mask.render_target = "*jaegFACE"
	hair.overlays += mask
	hair.filters += filter(type = "alpha", x = 0, y = 0, render_source = "*jaegFACE")
	overlays += hair

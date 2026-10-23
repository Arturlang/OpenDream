#define PLANE_SPACE -21
#define APPEARANCE_UI (RESET_COLOR|RESET_TRANSFORM|NO_CLIENT_COLOR|PIXEL_SCALE)
#define PLANE_SPACE_PARALLAX -20

/world
	view = "15x15"
	maxx = 30
	maxy = 30
	maxz = 1
	turf = /turf/space
	mob = /mob/viewer
	icon_size = 32

/turf/space
	icon = 'tiles.dmi'
	icon_state = "white"
	plane = PLANE_SPACE

/turf/floor
	icon = 'tiles.dmi'
	icon_state = "floor"

/obj/plane_space
	appearance_flags = PLANE_MASTER
	plane = PLANE_SPACE
	screen_loc = "CENTER"
	color = list(0,0,0,0, 0,0,0,0, 0,0,0,0, 1,1,1,1, 0,0,0,0)

/obj/plane_parallax
	appearance_flags = PLANE_MASTER
	plane = PLANE_SPACE_PARALLAX
	blend_mode = BLEND_MULTIPLY
	screen_loc = "CENTER"

/obj/parallax_home
	blend_mode = BLEND_ADD
	plane = PLANE_SPACE_PARALLAX
	screen_loc = "CENTER-7,CENTER-7"

/obj/parallax_layer
	icon = 'parallax.dmi'
	icon_state = "layer1"
#ifdef NO_KT
	appearance_flags = APPEARANCE_UI
#else
	appearance_flags = APPEARANCE_UI | KEEP_TOGETHER
#endif
	blend_mode = BLEND_ADD
	plane = PLANE_SPACE_PARALLAX

/obj/parallax_layer/New()
	..()
	// update_o() for a 15x15 view: a 5x5 grid of 480px tiles minus the centre
	for(var/x in -2 to 2)
		for(var/y in -2 to 2)
			if(x == 0 && y == 0)
				continue
			var/mutable_appearance/tile = new
			tile.plane = FLOAT_PLANE
			tile.layer = FLOAT_LAYER
			tile.icon = icon
			tile.icon_state = icon_state
#ifdef USE_PIXEL_XY
			tile.pixel_x = 480 * x
			tile.pixel_y = 480 * y
#else
			tile.pixel_w = 480 * x
			tile.pixel_z = 480 * y
#endif
			overlays += tile
	pixel_w = -137
	pixel_z = -91

/mob/viewer/Login()
	..()
#ifdef CLIENT_FPS
	client.fps = CLIENT_FPS
#endif
	loc = locate(15, 15, 1)
	// floor in the bottom-right quadrant so both space and non-space are on screen
	for(var/turf/T in block(locate(15, 1, 1), locate(30, 14, 1)))
		new /turf/floor(T)
	var/obj/parallax_home/home = new
	home.vis_contents += new /obj/parallax_layer
	client.screen += list(new /obj/plane_space, new /obj/plane_parallax, home)

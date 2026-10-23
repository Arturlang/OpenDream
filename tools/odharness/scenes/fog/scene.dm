#define LOS_RANGE 8
#define MOVE_DELAY 5
#define FADE_TIME 3
#define LOSVIS_PLANE 10
#define REVEAL_PLANE 11
#define FOG_PLANE 20

/world
	fps = 20
	view = "27x21"
	maxx = 40
	maxy = 30
	maxz = 1
	turf = /turf/floor
	mob = /mob/viewer
	icon_size = 32

var/global/client/viewer_client
var/global/list/vis_count = list()
var/global/list/markers = list()
var/global/list/tile_statics = list()

/turf/floor
	icon = 'tiles.dmi'
	icon_state = "floor"

/turf/wall
	icon = 'tiles.dmi'
	icon_state = "wall"
	density = TRUE
	opacity = TRUE

/world/New()
	..()
	for(var/x in 1 to world.maxx)
		new /turf/wall(locate(x, 1, 1))
		new /turf/wall(locate(x, world.maxy, 1))
	for(var/y in 1 to world.maxy)
		new /turf/wall(locate(1, y, 1))
		new /turf/wall(locate(world.maxx, y, 1))
	for(var/x in 2 to world.maxx - 1)
		if(x == 10 || x == 25 || x == 34)
			continue
		new /turf/wall(locate(x, 15, 1))
	for(var/y in 16 to world.maxy - 1)
		if(y == 22)
			continue
		new /turf/wall(locate(20, y, 1))
	for(var/x in 7 to 8)
		for(var/y in 6 to 7)
			new /turf/wall(locate(x, y, 1))
	for(var/x in 28 to 30)
		for(var/y in 8 to 9)
			new /turf/wall(locate(x, y, 1))
	new /obj/door(locate(25, 15, 1))
	new /obj/door(locate(20, 22, 1))

/obj/door
	icon = 'tiles.dmi'
	icon_state = "door_closed"
	density = TRUE
	opacity = TRUE

/obj/door/New()
	..()
	spawn(20)
		while(src)
			sleep(30)
			density = !density
			opacity = !opacity
			icon_state = density ? "door_closed" : "door_open"
			for(var/mob/marine/M in range(LOS_RANGE + 1, src))
				M.update_los()

/mob/viewer
	invisibility = 101
	density = FALSE
	sight = SEE_TURFS | SEE_MOBS | SEE_OBJS

/mob/viewer/Login()
	..()
	loc = locate(20, 15, 1)
	viewer_client = client
#ifdef TILE_STATIC
	for(var/turf/T in world)
		var/image/I = image('tiles.dmi', T, "tile_static")
		I.plane = FOG_PLANE
		tile_statics[T] = I
		client.images += I
#else
	client.screen += new /obj/pm/losvis
	client.screen += new /obj/pm/reveal
	client.screen += new /obj/pm/fog
	client.screen += new /obj/fog
#endif
	spawn(10)
		start_marines()

/obj/pm
	appearance_flags = PLANE_MASTER
	screen_loc = "CENTER"
	mouse_opacity = 0

/obj/pm/losvis
	plane = LOSVIS_PLANE
	render_target = "*losvis"

/obj/pm/reveal
	plane = REVEAL_PLANE
	render_target = "*reveal"

/obj/pm/reveal/New()
	..()
#ifndef NO_LOS
	filters += filter(type = "alpha", render_source = "*losvis")
#endif

/obj/pm/fog
	plane = FOG_PLANE

/obj/pm/fog/New()
	..()
	filters += filter(type = "alpha", render_source = "*reveal", flags = MASK_INVERSE)

/obj/fog
	icon = 'static.dmi'
	icon_state = "static"
	plane = FOG_PLANE
	screen_loc = "SOUTHWEST to NORTHEAST"
	mouse_opacity = 0

/proc/start_marines()
	var/list/routes = list(
		list(locate(5, 4, 1), locate(35, 4, 1), locate(35, 12, 1), locate(5, 12, 1)),
		list(locate(10, 10, 1), locate(10, 20, 1), locate(15, 26, 1), locate(10, 20, 1)),
		list(locate(25, 11, 1), locate(25, 19, 1), locate(30, 26, 1), locate(25, 19, 1)),
		list(locate(34, 6, 1), locate(34, 20, 1), locate(37, 27, 1), locate(34, 20, 1)),
		list(locate(14, 3, 1), locate(31, 3, 1)),
		list(locate(18, 25, 1), locate(22, 22, 1), locate(27, 22, 1), locate(22, 22, 1)),
	)
	for(var/list/route in routes)
		var/mob/marine/M = new(route[1])
		M.route = route
		M.update_los()
		spawn(rand(0, MOVE_DELAY))
			M.patrol()

/mob/marine
	icon = 'tiles.dmi'
	icon_state = "marine"
	density = FALSE
	glide_size = 32 / MOVE_DELAY
	var/list/route
	var/route_index = 1
	var/list/seen = list()

/mob/marine/New()
	..()
#if !defined(TILE_STATIC)
	var/mutable_appearance/reveal = new
	reveal.icon = 'reveal.dmi'
	reveal.icon_state = "reveal"
	reveal.plane = REVEAL_PLANE
	reveal.pixel_x = -224
	reveal.pixel_y = -224
	reveal.appearance_flags = RESET_COLOR | RESET_ALPHA | RESET_TRANSFORM | KEEP_APART
	overlays += reveal
#endif

/mob/marine/proc/patrol()
	while(src)
		sleep(MOVE_DELAY * world.tick_lag)
		var/turf/target = route[route_index]
		if(loc == target)
			route_index = route_index % length(route) + 1
			continue
		var/turf/old_loc = loc
		step_to(src, target)
		if(loc != old_loc)
			update_los()

/mob/marine/proc/update_los()
	var/list/now = list()
	for(var/turf/T in view(LOS_RANGE, src))
		now[T] = TRUE
	for(var/turf/T as anything in seen - now)
		var/count = vis_count[T] - 1
		vis_count[T] = count
		if(count <= 0)
			hide_turf(T)
	for(var/turf/T as anything in now - seen)
		var/count = vis_count[T] + 1
		vis_count[T] = count
		if(count == 1)
			show_turf(T)
	seen = now

/proc/show_turf(turf/T)
#ifdef TILE_STATIC
	var/image/I = tile_statics[T]
	if(I)
		I.alpha = 0
#else
	var/image/M = markers[T]
	if(!M)
		M = image('marker.dmi', T, "marker")
		M.plane = LOSVIS_PLANE
		M.pixel_x = -16
		M.pixel_y = -16
		M.alpha = 0
		M.appearance_flags = RESET_COLOR | RESET_TRANSFORM | KEEP_APART
		markers[T] = M
		viewer_client?.images += M
	animate(M, alpha = 255, time = FADE_TIME * world.tick_lag)
#endif

/proc/hide_turf(turf/T)
#ifdef TILE_STATIC
	var/image/I = tile_statics[T]
	if(I)
		I.alpha = 255
#else
	var/image/M = markers[T]
	if(M)
		animate(M, alpha = 0, time = FADE_TIME * world.tick_lag)
#endif

// TGMC's jump: a translucent drop shadow filter, a parallel pixel_z animation with circular easing,
// and the shadow filter animated alongside. Left: static shadow. Middle: jumping (slowed). Right: plain.
#define COLOR_TRANSPARENT_SHADOW "#03020781"
#define JUMP_HEIGHT 24
#define JUMP_DURATION 60

/world
	view = 3
	maxx = 7
	maxy = 7
	maxz = 1
	fps = 20
	turf = /turf/floor
	mob = /mob/viewer

/turf/floor
	icon = 'tiles.dmi'
	icon_state = "floor"

/mob/viewer
	invisibility = 101

/obj/jumper
	icon = 'ghost.dmi'
	icon_state = "ghost"
	dir = SOUTH

/mob/viewer/Login()
	..()
	loc = locate(4, 4, 1)
	var/obj/jumper/still = new(locate(2, 4, 1))
	still.filters += filter(type = "drop_shadow", size = 0.9, color = COLOR_TRANSPARENT_SHADOW)
	new /obj/jumper(locate(6, 4, 1))
	var/obj/jumper/J = new(locate(4, 4, 1))
	spawn(0)
		while(J)
			jump(J)
			sleep(JUMP_DURATION + 10)

/proc/jump(atom/movable/jumper)
	jumper.filters += filter(type = "drop_shadow", size = 0.9, color = COLOR_TRANSPARENT_SHADOW)
	var/shadow = jumper.filters[length(jumper.filters)]
	animate(jumper, pixel_z = JUMP_HEIGHT, time = JUMP_DURATION / 2, easing = CIRCULAR_EASING|EASE_OUT, flags = ANIMATION_END_NOW|ANIMATION_PARALLEL)
	animate(pixel_z = 0, time = JUMP_DURATION / 2, easing = CIRCULAR_EASING|EASE_IN)
	animate(shadow, y = -JUMP_HEIGHT, size = 4, time = JUMP_DURATION / 2, easing = CIRCULAR_EASING|EASE_OUT, flags = ANIMATION_PARALLEL)
	animate(y = 0, size = 0.9, time = JUMP_DURATION / 2, easing = CIRCULAR_EASING|EASE_IN)
	spawn(JUMP_DURATION)
		jumper.filters = null

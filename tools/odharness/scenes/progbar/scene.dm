// TGMC's do_after visuals: a KEEP_APART busy icon overlaid on a KEEP_TOGETHER mob, and a progress bar image
// on ABOVE_HUD_PLANE sitting above the target, raised with pixel_z and animated in
#define APPEARANCE_UI (RESET_COLOR|RESET_TRANSFORM|NO_CLIENT_COLOR|PIXEL_SCALE)
#define APPEARANCE_UI_IGNORE_ALPHA (RESET_COLOR|RESET_TRANSFORM|NO_CLIENT_COLOR|RESET_ALPHA|PIXEL_SCALE)
#define ABOVE_HUD_PLANE 36

/world
	view = 3
	maxx = 7
	maxy = 7
	maxz = 1
	fps = 20
	turf = /turf/floor
	mob = /mob/doer

/turf/floor
	icon = 'tiles.dmi'
	icon_state = "floor"

/mob/doer
	icon = 'ghost.dmi'
	icon_state = "ghost"
	appearance_flags = KEEP_TOGETHER|TILE_BOUND|PIXEL_SCALE

/image/progress
	icon = 'progressbar.dmi'
	plane = ABOVE_HUD_PLANE
	appearance_flags = APPEARANCE_UI_IGNORE_ALPHA

/image/progress/bar
	icon_state = "prog_bar_1"
	alpha = 0

/image/progress/frame
	icon_state = "prog_bar_1_frame"
	appearance_flags = APPEARANCE_UI

/image/progdisplay
	icon = 'progressicons.dmi'
	icon_state = "busy_generic"
#ifdef NO_KEEP_APART
	appearance_flags = APPEARANCE_UI|TILE_BOUND
#else
	appearance_flags = APPEARANCE_UI|KEEP_APART|TILE_BOUND
#endif
#ifdef USE_PIXEL_Y
	pixel_y = 32
#else
	pixel_z = 32
#endif

/mob/doer/Login()
	..()
	loc = locate(3, 4, 1)
	var/mob/doer/target = new(locate(5, 4, 1))
	overlays += new /image/progdisplay
	var/image/progress/bar/bar = new
	bar.loc = target
	bar.pixel_z += 32 - 6
	bar.overlays += /image/progress/frame
	animate(bar, pixel_z = bar.pixel_z + 6, alpha = 255, time = 5, easing = SINE_EASING)
	client.images += bar
	spawn(0)
		var/progress = 0
		while(bar)
			progress = (progress + 5) % 105
			bar.icon_state = "prog_bar_1_[progress]"
			sleep(2)

// Render pages: the 25x17 view holds 7x5 cells of 3x3 tiles on a checkered background, four magenta corner
// markers (screen objects) for the comparer to find the map by, and a page code tile coloured from the page
// number. "cmd=page&n=N" (world Topic) clears the previous page and builds page N from the generated
// render_build_page() in cases.dm. Everything a cell creates must go through parity_track().

#define RENDER_COLS 7
#define RENDER_ROWS 5
#define RENDER_MARKER_PLANE 10000

/turf
	icon = 'render.dmi'
	icon_state = "bg"

/obj/render_marker
	icon = 'render.dmi'
	icon_state = "marker"
	plane = RENDER_MARKER_PLANE
	appearance_flags = RESET_COLOR | RESET_ALPHA | RESET_TRANSFORM | NO_CLIENT_COLOR
	mouse_opacity = 0

/obj/render_marker/code
	icon_state = "code"

var/global/obj/render_marker/code/render_code
var/global/render_page_n = 0

/proc/live_suite_login(client/C)
	var/mob/M = C.mob
	M.loc = locate(13, 9, 1)
	C.eye = M
	for(var/loc in list("1,1", "25,1", "1,17", "25,17"))
		var/obj/render_marker/O = new
		O.screen_loc = loc
		C.screen += O
	render_code = new
	render_code.screen_loc = "2,17"
	C.screen += render_code

/proc/live_suite_command(cmd, list/P)
	if(cmd == "page")
		var/n = text2num(P["n"])
		parity_cleanup()
		render_reset_client()
		render_page_n = n
		// Page n shows as rgb(n % 256, round(n / 256), 77) in the code tile
		render_code.color = rgb(n % 256, round(n / 256) % 256, 77)
		var/count = render_build_page(n)
		return "ok page=[n] cells=[count]"
	return "ERR unknown cmd [cmd]"

// Solo cells change client state. Each page starts from the login state.
/proc/render_reset_client()
	var/client/C = live_client
	C.color = null
	C.mob.see_invisible = initial(C.mob.see_invisible)
	for(var/atom/movable/A in C.screen)
		if(!istype(A, /obj/render_marker))
			C.screen -= A

// Centre turf of cell i (0-based, left to right, top row first)
/proc/render_cell_turf(i)
	var/c = i % RENDER_COLS
	var/r = RENDER_ROWS - 1 - round(i / RENDER_COLS)
	return locate(4 + 3 * c, 2 + 3 * r, 1)

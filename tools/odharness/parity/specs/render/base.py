"""Render suite: shared DM helpers. The other files of this suite use them."""

HELPERS = r"""
// Makes a tracked obj on T with an icon and a state
/proc/render_x_obj(turf/T, state = "asym", icn = 'test.dmi')
	var/obj/O = parity_track(new /obj(T))
	O.icon = icn
	O.icon_state = state
	return O

// Makes a tracked obj with no loc, for vis_contents
/proc/render_x_free(state = "asym", icn = 'test.dmi')
	var/obj/O = parity_track(new /obj)
	O.icon = icn
	O.icon_state = state
	return O

var/global/list/render_x_masters = list()

// Puts a tracked plane master on the screen of the client
/proc/render_x_master(p)
	var/obj/O = parity_track(new /obj)
	O.appearance_flags = PLANE_MASTER
	O.plane = p
	O.screen_loc = "1,1"
	render_x_masters += O
	if(live_client)
		live_client.screen += O
	return O

// Puts back the view state that solo cells change when the page is cleared
/datum/render_x_restore
	var/old_color
	var/old_see

/datum/render_x_restore/New()
	if(live_client)
		old_color = live_client.color
		old_see = live_client.mob.see_invisible

/datum/render_x_restore/Del()
	if(live_client)
		live_client.color = old_color
		live_client.mob.see_invisible = old_see
		live_client.screen -= render_x_masters
	render_x_masters.Cut()
	..()

/proc/render_x_solo()
	parity_track(new /datum/render_x_restore)
"""


def build(s):
    s.render()
    s.dm(HELPERS.strip("\n"))

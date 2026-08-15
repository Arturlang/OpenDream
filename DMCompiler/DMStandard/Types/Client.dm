/client
	var/list/verbs = null
	var/list/screen = null
	var/list/images = null
	var/list/vars

	var/atom/statobj
	var/statpanel
	var/default_verb_category = "Commands"

	var/tag
	var/const/type = /client

	var/mob/mob // TODO: as /mob|null
	var/atom/eye
	var/lazy_eye = 0
	var/perspective = MOB_PERSPECTIVE
	var/edge_limit = null
	var/view
	var/pixel_x = 0
	var/pixel_y = 0
	var/pixel_z = 0
	var/pixel_w = 0
	var/show_popup_menus = 1
	var/show_verb_panel = 1

	var/byond_version = DM_VERSION
	var/byond_build = DM_BUILD

	var/address
	var/inactivity = 0
	var/key as text|null
	var/ckey as text|null
	var/connection
	var/computer_id = 0
	var/tick_lag = 0
	var/authenticate = TRUE as opendream_unimplemented // TODO: auth.mode CVar

	var/timezone

	var/script
	var/color = 0
	var/control_freak
	var/mouse_pointer_icon
	var/preload_rsc = 1
	var/fps = 0
	var/dir = NORTH
	var/gender = NEUTER as text|opendream_unsupported
	var/glide_size
	var/virtual_eye
	
	var/list/bounds
	var/bound_x
	var/bound_y
	var/bound_width
	var/bound_height

	proc/New(TopicData)
		// Search every mob for one with our ckey
		// TODO: This /mob|mob thing is kinda silly huh?
		for (var/mob/M as /mob|mob in world)
			if (M.key == key)
				mob = M
				break

		if (mob == null) // No existing mob, create a default one
			var/mob/initial_mob = new world.mob()
			
			eye = initial_mob
			statobj = initial_mob
			mob = initial_mob
		return mob

	proc/Del()

	proc/Topic(href, list/href_list, datum/hsrc)
		if (hsrc != null)
			hsrc.Topic(href, href_list)

	proc/Stat()
		if (istype(statobj, /atom))
			statobj.Stat()

	proc/Command(command as command_text)

	proc/Import(Query)
	proc/Export(file)
	proc/AllowUpload(filename, filelength)
		return TRUE

	proc/SoundQuery()
	proc/MeasureText(text, style, width=0)

	proc/Move(loc, dir)
		mob.Move(loc, dir)

	verb/North()
		set name = ".north"
		Move(get_step(mob, NORTH), NORTH)

	verb/South()
		set name = ".south"
		Move(get_step(mob, SOUTH), SOUTH)

	verb/East()
		set name = ".east"
		Move(get_step(mob, EAST), EAST)

	verb/West()
		set name = ".west"
		Move(get_step(mob, WEST), WEST)

	verb/Northeast()
		set name = ".northeast"
		Move(get_step(mob, NORTHEAST), NORTHEAST)

	verb/Southeast()
		set name = ".southeast"
		Move(get_step(mob, SOUTHEAST), SOUTHEAST)

	verb/Southwest()
		set name = ".southwest"
		Move(get_step(mob, SOUTHWEST), SOUTHWEST)

	verb/Northwest()
		set name = ".northwest"
		Move(get_step(mob, NORTHWEST), NORTHWEST)

	verb/Center()
		set name = ".center"
		//TODO: walk(usr, 0)

	proc/Click(atom/object, location, control, params)
		object.Click(location, control, params)

	proc/DblClick(atom/object, location, control, params)
		object.DblClick(location,control,params)

	proc/MouseDown(atom/object, location, control, params)
		object.MouseDown(location, control, params)

	proc/MouseDrag(atom/src_object,over_object,src_location,over_location,src_control,over_control,params)
		src_object.MouseDrag(over_object,src_location,over_location,src_control,over_control,params)

	proc/MouseDrop(atom/src_object,over_object,src_location,over_location,src_control,over_control,params)
		src_object.MouseDrop(over_object,src_location,over_location,src_control,over_control,params)

	proc/MouseEntered(atom/object,location,control,params)
		object.MouseEntered(location,control,params)

	proc/MouseExited(atom/object,location,control,params)
		object.MouseExited(location,control,params)

	proc/MouseMove(atom/object,location,control,params)
		object.MouseMove(location,control,params)

	proc/MouseUp(atom/object,location,control,params)
		object.MouseUp(location,control,params)

	proc/MouseWheel(atom/object,delta_x,delta_y,location,control,params)
		object.MouseWheel(delta_x,delta_y,location,control,params)

	proc/IsByondMember()
		set opendream_unsupported = "OpenDream has no premium tier."
		return FALSE
	proc/CheckPassport(passport_identifier)
		set opendream_unsupported = "OpenDream does not support subscribing to games"
	proc/SendPage(msg, recipient, options)
		set opendream_unsupported = "OpenDream does not implement a pager"
	proc/GetAPI(Api, Name)
		set opendream_unsupported = "Steam Achievements API will not be supported"
	proc/SetAPI(Api, Key, Value)
		set opendream_unsupported = "Steam Achievements API will not be supported"
	proc/RenderIcon(object)
		return object

/atom
	parent_type = /datum

	var/name = null
	var/text = null
	var/desc = null
	var/suffix = null

	// The initialization/usage of these lists is handled internally by the runtime
	var/tmp/list/verbs = null
	var/list/contents = null
	var/list/overlays = null
	var/list/underlays = null
	var/tmp/list/vis_locs = null
	var/list/vis_contents = null

	var/tmp/atom/loc
	var/dir = SOUTH
	var/tmp/x = 0
	var/tmp/y = 0
	var/tmp/z = 0
	var/pixel_x = 0
	var/pixel_y = 0
	var/pixel_z = 0
	var/pixel_w = 0
	
	var/icon_w = 0
	var/icon_z = 0

	var/icon = null as icon|null
	var/icon_state = null as text|null
	var/layer = 2.0
	var/plane = 0
	var/alpha = 255
	var/color = null as /list|text|null
	var/invisibility = 0
	var/mouse_opacity = 1
	var/infra_luminosity = 0
	var/luminosity = 0
	var/opacity = 0
	var/matrix/transform
	var/blend_mode = 0

	var/gender = NEUTER
	var/density = FALSE

	var/maptext = null

	var/list/filters = null
	var/appearance
	var/appearance_flags = 0
	var/maptext_width = 32
	var/maptext_height = 32 
	var/maptext_x = 0
	var/maptext_y = 0
	var/step_x
	var/step_y
	var/render_source
	var/tmp/mouse_drag_pointer 
	var/tmp/mouse_drop_pointer = MOUSE_ACTIVE_POINTER
	var/tmp/mouse_over_pointer
	var/mouse_drop_zone = FALSE
	var/render_target
	var/vis_flags
	var/pixloc/pixloc

	proc/Click(location, control, params)
	proc/DblClick(location, control, params)
	proc/MouseDrop(over_object,src_location,over_location,src_control,over_control,params)
	proc/MouseEntered(location,control,params)
	proc/MouseExited(location,control,params)

	proc/MouseDown(location, control, params)

	proc/MouseDrag(over_object,src_location,over_location,src_control,over_control,params)

	proc/MouseMove(location,control,params)

	proc/MouseUp(location,control,params)

	proc/MouseWheel(delta_x,delta_y,location,control,params)

	proc/Entered(atom/movable/Obj, atom/OldLoc)
	proc/Exited(atom/movable/Obj, atom/newloc)
	proc/Uncrossed(atom/movable/O)
	proc/Crossed(atom/movable/O)

	proc/Cross(atom/movable/O)
		// Allow crossing only if not both atoms are dense
		return !(src.density && O.density)

	proc/Uncross(atom/movable/O)
		return TRUE

	proc/Enter(atom/movable/O, atom/oldloc)
		return TRUE

	proc/Exit(atom/movable/O, atom/newloc)
		return TRUE

	proc/Stat()
	
	New(loc)
		..()

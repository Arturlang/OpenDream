/atom/movable
	var/screen_loc

	var/animate_movement = FORWARD_STEPS
	var/list/locs = null
	var/glide_size = 0
	var/step_size
	var/tmp/bound_x
	var/tmp/bound_y
	var/tmp/bound_width
	var/tmp/bound_height

	//Undocumented var. "[x],[y]" or "[x],[y] to [x2],[y2]" based on bound_* vars
	var/bounds

	var/particles/particles 

	proc/Bump(atom/Obstacle)

	proc/Move(atom/NewLoc, Dir=0) as num
		if (isnull(NewLoc) || loc == NewLoc)
			return FALSE

		if (Dir != 0)
			dir = Dir
		
		var/area/oldarea = isarea(loc?.loc) ? loc.loc : null
		var/area/newarea = isarea(NewLoc.loc) ? NewLoc.loc : null
		var/consider_area = (oldarea != newarea)

		if (!isnull(loc))
			// Loc first
			if (!loc.Exit(src, NewLoc))
				return FALSE
			// Area second
			if (consider_area && !isnull(oldarea) && !oldarea.Exit(src, NewLoc))
				return FALSE
			// Ensure the atoms on the turf also permit this exit
			for (var/atom/movable/exiting in loc)
				if (exiting != src)
					if (!exiting.Uncross(src))
						return FALSE

		var/loc_entered = NewLoc.Enter(src, loc)
		var/area_entered = !consider_area || isnull(newarea) || newarea.Enter(src, loc)
		if (!loc_entered || !area_entered)
			if (!area_entered)
				src.Bump(newarea)
			if (!loc_entered)
				for (var/atom/content in NewLoc.contents)
					src.Bump(content)
					
			return FALSE
		else
			var/atom/oldloc = loc
			loc = NewLoc

			// First, call Exited() on the old turf and Uncrossed() on its contents
			oldloc?.Exited(src, loc)
			for (var/atom/movable/uncrossed in oldloc)
				uncrossed.Uncrossed(src)
			
			// Second, call Exited() on the old area
			if (consider_area)
				oldarea?.Exited(src, loc)

			// Third, call Entered() on the new turf and Crossed() on its contents
			loc.Entered(src, oldloc)
			for (var/atom/movable/crossed in loc)
				if(crossed != src)
					crossed.Crossed(src)

			// Fourth, call Entered() on the new area
			if (consider_area)
				newarea?.Entered(src, oldloc)

			return TRUE

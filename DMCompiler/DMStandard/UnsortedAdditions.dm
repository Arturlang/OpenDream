/proc/bounds(Ref=src, Dist=0)
	return range(Dist, Ref)

// An undocumented proc
// Doesn't evaluate DM as you might expect, but instead DMScript
/proc/eval(script)
	set opendream_unsupported = "eval() is officially deprecated"

/proc/ispointer(Value)
	set opendream_unimplemented = TRUE
	return FALSE

/proc/load_resource(File)
proc/missile(Type, Start, End)

/proc/obounds(Ref=src, Dist=0)
	return orange(Dist, Ref)
/proc/run(File)
/proc/shell(command)
/proc/bound_pixloc(var/atom/Atom, var/Dir as num)
	if (!istype(Atom))
		return null
	if (Atom.z <= 0)
		return null

	var/left = ((Atom.x - 1) * world.icon_size) + (Atom.step_x || 0) + Atom:bound_x + 1
	var/right = left + Atom:bound_width
	var/bottom = ((Atom.y - 1) * world.icon_size) + (Atom.step_y || 0) + Atom:bound_y + 1
	var/top = bottom + Atom:bound_height

	var/pixel_x
	if (Dir & EAST)
		pixel_x = right
	else if (Dir & WEST)
		pixel_x = left
	else
		pixel_x = (left + right) / 2

	var/pixel_y
	if (Dir & NORTH)
		pixel_y = top
	else if (Dir & SOUTH)
		pixel_y = bottom
	else
		pixel_y = (bottom + top) / 2

	var/pixloc/result = pixloc(pixel_x, pixel_y, Atom.z)
	return result

/proc/_dm_db_new_con(filename)
/proc/_dm_db_connect(database, filename)
/proc/_dm_db_close(database)
/proc/_dm_db_is_connected(database)
/proc/_dm_db_quote(value, flags)
/proc/_dm_db_new_query(text, ...)
/proc/_dm_db_execute(query, database, a, b, c)
/proc/_dm_db_next_row(query, a, b)
/proc/_dm_db_rows_affected(query)
/proc/_dm_db_row_count(query)
/proc/_dm_db_error_msg(database_or_query)
/proc/_dm_db_columns(query, column)

// TGMC's held-key bookkeeping (bindings_client.dm / bindings_atom.dm), logged after every key event
#ifdef OPENDREAM
#define ENGINE "od"
#else
#define ENGINE "byond"
#endif
#define HELD_KEY_BUFFER_LENGTH 15

/world
	view = 7
	maxx = 15
	maxy = 15
	maxz = 1
	turf = /turf/floor
	mob = /mob/walker

/turf/floor
	icon = 'tiles.dmi'
	icon_state = "floor"

/mob/walker
	icon = 'tiles.dmi'
	icon_state = "white"

/client
	var/list/keys_held = list()
	var/list/movement_keys = list("W" = NORTH, "A" = WEST, "S" = SOUTH, "D" = EAST)
	var/intended_direction = 0
	var/next_move_dir_add = 0
	var/next_move_dir_sub = 0

/client/proc/note(text)
	text2file("[world.time]\t[text]\tlen=[length(keys_held)]\theld=[json_encode(keys_held)]\tintended=[intended_direction]", "events_[ENGINE].txt")

/client/proc/calculate_move_dir()
	var/movement_dir = 0
	for(var/_key in keys_held)
		movement_dir |= movement_keys[_key]
	intended_direction = movement_dir

/client/verb/keyDown(_key as text)
	set instant = TRUE
	set hidden = TRUE
	if(length(keys_held) >= HELD_KEY_BUFFER_LENGTH && !keys_held[_key])
		keyUp(keys_held[1])
	keys_held[_key] = world.time
	var/movement = movement_keys[_key]
	if(movement)
		calculate_move_dir()
		if(!(next_move_dir_sub & movement))
			next_move_dir_add |= movement
	note("down [_key]")

/client/verb/keyUp(_key as text)
	set instant = TRUE
	set hidden = TRUE
	for(var/i in 1 to length(keys_held))
		if(keys_held[i] == _key)
			keys_held[i] = null
			break
	keys_held -= _key
	var/movement = movement_keys[_key]
	if(movement)
		calculate_move_dir()
		if(!(next_move_dir_add & movement))
			next_move_dir_sub |= movement
	note("up [_key]")

/mob/walker/Login()
	..()
	loc = locate(8, 8, 1)
	fdel("events_[ENGINE].txt")

// Hammers proc calls and datum churn for profiling the interpreter's call path
/world
	maxx = 5
	maxy = 5
	maxz = 1
	loop_checks = 0

/proc/noop(a, b)
	return a

/datum/thing
	var/value = 1
/datum/thing/proc/get()
	return value

/world/New()
	..()
	spawn(10)
		var/start = world.timeofday
		var/x
		var/datum/thing/T = new
		while(world.timeofday - start < 400)
			for(var/i in 1 to 10000)
#ifndef NEW_ONLY
				x = noop(i, 2)
				x = T.get()
#endif
#ifndef CALLS_ONLY
				x = new /datum/thing
#endif
		world.log << "CALLBENCH DONE [x]"
		shutdown()

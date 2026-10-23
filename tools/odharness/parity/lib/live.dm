// Live suites (rendering pages, browser probes, prompts): the world stays up with a client connected and the
// harness drives it with world Topic calls ("cmd=<name>&..."), so nothing needs keyboard focus or clicks.
// A live suite defines /proc/live_suite_command(cmd, list/P) in its s.dm() code and returns text for the reply.

#ifndef LIVE_VIEW
#define LIVE_VIEW "25x17"
#endif

/world
	mob = /mob/live_viewer

var/global/client/live_client

/mob/live_viewer
	invisibility = 101
	density = 0

/mob/live_viewer/Login()
	..()
	live_client = client
	client.view = LIVE_VIEW
	client.perspective = EYE_PERSPECTIVE
	live_login(client)
	text2file("#CLIENT\t[PARITY_ENGINE]\n", PARITY_OUT)

/proc/live_login(client/C)
	live_suite_login(C)

/world/Topic(T, Addr, Master, Keys)
	var/list/P = params2list(T)
	var/cmd = P["cmd"]
	switch(cmd)
		if("ping")
			return "pong [PARITY_ENGINE] client=[live_client ? 1 : 0]"
		if("quit")
			spawn(1)
				shutdown()
			return "bye"
	var/r
	try
		r = live_suite_command(cmd, P)
	catch(var/exception/e)
		r = "ERR [e.name]"
	return isnull(r) ? "ok" : "[r]"

// Skin suites: the cases run only while a client is connected, so winset(), winget(), winclone() and winshow()
// act on a real skin. "cmd=run" (world Topic) starts them. Cases use live_client for the client.

#ifndef SKIN_CASE_TICKS
#define SKIN_CASE_TICKS 30
#endif

var/global/list/parity_results = list()

/proc/live_suite_login(client/C)
	return

/proc/parity_err_text(exception/e)
	return "ERR [parity_escape(istype(e) ? "[e.name]" : "[e]")]"

// Runs one case proc in its own thread and waits up to SKIN_CASE_TICKS for its result
/proc/parity_timed(case_proc, id)
	if(parity_skipped(id))
		return
	spawn(0)
		call(case_proc)()
	var/waited = 0
	while(isnull(parity_results[id]) && waited < SKIN_CASE_TICKS)
		sleep(1)
		waited++
	if(isnull(parity_results[id]))
		parity_emit_raw(id, "TIMEOUT")
	else
		parity_emit_raw(id, parity_results[id])

/proc/live_suite_command(cmd, list/P)
	if(cmd == "run")
		spawn(0)
			parity_run_chunks()
			text2file("#DONE\n", PARITY_OUT)
		return "ok"
	return "ERR unknown cmd [cmd]"

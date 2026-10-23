// Prompt suites. "cmd=ask&i=N" starts prompt case N (prompt_run() in cases.dm) and returns at once.
// The case blocks on its prompt until the harness answers it, then writes its result line.

/proc/live_suite_login(client/C)
	return

/proc/live_suite_command(cmd, list/P)
	if(cmd == "ask")
		var/i = text2num(P["i"])
		spawn(0)
			prompt_run(i, live_client)
		return "ok"
	return "ERR unknown cmd [cmd]"

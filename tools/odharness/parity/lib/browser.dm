// Browser probe suites: "cmd=start" (world Topic) shows probe.html in the skin's "probe" browser control.
// The page runs every probe in order and reports each result through a byond:// link that lands in
// client/Topic below. The server acknowledges with output(), so the page sends one message at a time.
//   parity_probe=<id>&v=<json>   a value the page measured           -> "<id>\tj:<json>"
//   parity_req=<id>              DM runs browser_request(id, C) (generated), which calls output() back
//   parity_link=<id>&...         a link-encoding probe: the parsed href_list is recorded -> "<id>:dm\t<canon>"
//   parity_done=1                all probes ran                      -> "#PROBES_DONE"

var/global/browser_started = 0

/proc/live_suite_login(client/C)
	return

/proc/live_suite_command(cmd, list/P)
	if(cmd == "start")
		var/page = file2text("probe.html")
		live_client << browse(page, "window=probe")
		browser_started = 1
		return "ok"
	return "ERR unknown cmd [cmd]"

/proc/browser_ack(client/C)
	C << output("1", "probe:parity_ack")

/client/Topic(href, list/href_list, hsrc)
	if(href_list["parity_probe"])
		parity_emit_raw(href_list["parity_probe"], "j:[parity_escape(href_list["v"])]")
		browser_ack(src)
		return
	if(href_list["parity_link"])
		var/id = href_list["parity_link"]
		var/list/L = href_list.Copy()
		L -= "parity_link"
		parity_emit_raw("[id]:dm", parity_canon(L))
		parity_emit_raw("[id]:href", parity_canon(href))
		browser_ack(src)
		return
	if(href_list["parity_req"])
		var/id = href_list["parity_req"]
		try
			browser_request(id, src)
		catch(var/exception/e)
			parity_emit_raw("[id]:dm", "ERR [parity_escape(e.name)]")
		return
	if(href_list["parity_done"])
		text2file("#PROBES_DONE\n", PARITY_OUT)
		return
	..()

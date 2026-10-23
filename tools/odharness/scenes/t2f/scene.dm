/world/New()
	..()
	var/list/r = list()
	var/list/L = list()
	L["D"] = 1
	L["W"] = 2
	L[1] = null
	r += "after L\[1]=null: len=[L.len] D=[isnull(L["D"]) ? "null" : L["D"]] W=[L["W"]]"
	L -= "D"
	r += "after -= D: len=[L.len]"
	L["D"] = 5
	r += "after D=5: len=[L.len] D=[L["D"]] json=[json_encode(L)]"
	var/list/M = list("D", "D")
	M["D"] = 7
	M[1] = null
	r += "dup: len=[M.len] D=[isnull(M["D"]) ? "null" : M["D"]] json=[json_encode(M)]"
	fdel("res.txt")
	text2file(jointext(r, "\n"), "res.txt")
	shutdown()

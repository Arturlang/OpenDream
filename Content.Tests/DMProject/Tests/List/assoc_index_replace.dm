// Replacing an item by index drops its association, so assigning the key again adds it back to the list
/proc/RunTest()
	var/list/L = list()
	L["D"] = 1
	L["W"] = 2
	L[1] = null
	ASSERT(L.len == 2)
	ASSERT(isnull(L["D"]))
	ASSERT(L["W"] == 2)

	L -= "D"
	ASSERT(L.len == 2)

	L["D"] = 5
	ASSERT(L.len == 3)
	ASSERT(L[3] == "D")
	ASSERT(L["D"] == 5)

	// Even when another copy of the key is still in the list
	var/list/M = list("D", "D")
	M["D"] = 7
	M[1] = null
	ASSERT(M.len == 2)
	ASSERT(isnull(M["D"]))
	ASSERT(M[2] == "D")

// Swap moves items with their associations
/proc/RunTest()
	var/list/L = list()
	L["a"] = 1
	L["b"] = 2
	L["c"] = 3
	L.Swap(1, 3)
	ASSERT(L[1] == "c")
	ASSERT(L[3] == "a")
	ASSERT(L["a"] == 1)
	ASSERT(L["b"] == 2)
	ASSERT(L["c"] == 3)

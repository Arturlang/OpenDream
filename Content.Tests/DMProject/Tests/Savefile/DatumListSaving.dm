/datum/entry
	var/choice = "default"

/proc/RunTest()
	var/savefile/S = new()

	var/datum/entry/A = new()
	A.choice = "first"
	var/datum/entry/B = new()
	B.choice = "second"

	S["prefs/entries"] << list(A, B)

	var/list/L
	S["prefs/entries"] >> L

	ASSERT(length(L) == 2)
	var/datum/entry/LA = L[1]
	var/datum/entry/LB = L[2]
	ASSERT(istype(LA) && LA != A)
	ASSERT(LA.choice == "first")
	ASSERT(LB.choice == "second")

	// Reading from inside a subdirectory exercises the lookup relative to the list, not the current dir
	S.cd = "prefs"
	S["entries"] >> L
	ASSERT(length(L) == 2)
	LB = L[2]
	ASSERT(LB.choice == "second")

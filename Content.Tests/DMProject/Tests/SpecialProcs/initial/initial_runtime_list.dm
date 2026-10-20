// initial() of a var initialized at runtime (e.g. list()) is an opaque truthy value in BYOND,
// which code uses to check whether a type sets such a var at all.
/datum/k
	var/list/l
	var/list/base_init = list(1)
	var/list/explicit_null = null
/datum/k/a
	l = list("W")
/datum/k/b
	l = null
/datum/k/c
	base_init = null

/proc/RunTest()
	var/datum/k/A = /datum/k/a
	var/datum/k/B = /datum/k/b
	var/datum/k/C = /datum/k/c
	var/datum/k/K = /datum/k

	var/v = initial(A.l)
	ASSERT(v)
	ASSERT(!isnull(v))
	ASSERT(!islist(v))
	ASSERT(!istext(v))
	ASSERT(!istype(v, /datum))
	ASSERT("[v]" == "")
	ASSERT(length(v) == 0)

	ASSERT(initial(K.base_init))
	ASSERT(initial(A.base_init)) // inherited
	ASSERT(isnull(initial(K.l)))
	ASSERT(isnull(initial(B.l))) // overridden to null
	ASSERT(isnull(initial(C.base_init))) // overridden to null
	ASSERT(isnull(initial(K.explicit_null)))

	var/datum/k/inst = new /datum/k/a
	ASSERT(initial(inst.l))

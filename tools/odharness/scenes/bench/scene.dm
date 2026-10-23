#ifdef OPENDREAM
#define ENGINE "od"
#else
#define ENGINE "byond"
#endif

/world
	view = 5
	maxx = 10
	maxy = 10
	maxz = 1
	loop_checks = 0

var/list/results = list()

// Runs BODY in a loop until at least ~1s has passed, then records the cost per iteration
#define BENCH(NAME, BODY) \
	do { \
		var/__n = 0; var/__start = world.timeofday; \
		while(world.timeofday - __start < 10) { for(var/__i in 1 to 100) { BODY; } __n += 100; } \
		results += "[NAME]\t[(world.timeofday - __start) * 100000 / __n]"; \
	} while(0)

/proc/noop(a, b)
	return a

/datum/thing
	var/value = 1
/datum/thing/proc/get()
	return value

// Real game types sit 6-8 levels deep and inherit most procs, which shallow types hide
/datum/thing/a/b/c/d/e/f/g

/world/New()
	..()
	spawn(10)
		run_benches()

/proc/run_benches()
	var/list/L = list()
	for(var/i in 1 to 1000)
		L += "item[i]"
	var/list/assoc = list()
	for(var/i in 1 to 1000)
		assoc["key[i]"] = i
	var/datum/thing/T = new
	var/icon/I = icon('tiles.dmi', "white")
	var/x

	BENCH("file2text small json", x = file2text("data/small.json"))
	BENCH("file2text large text", x = file2text("data/large.txt"))
	BENCH("json_decode small", x = json_decode(file2text("data/small.json")))
	BENCH("md5 file", x = md5(file("data/large.txt")))
	BENCH("md5 string", x = md5("hello world [rand()]"))
	BENCH("fcopy", x = fcopy("data/small.json", "data/copy.json"))
	BENCH("flist", x = flist("data/"))
	BENCH("fexists", x = fexists("data/small.json"))
	BENCH("icon GetPixel", x = I.GetPixel(5, 5))
	BENCH("copytext", x = copytext("#a1b2c3ff", 1, 8))
	var/y = 12345
	BENCH("string interpolate", x = "a[y]b")
	BENCH("findtext", x = findtext("the quick brown fox jumps", "jumps"))
	BENCH("splittext", x = splittext("a,b,c,d,e,f,g,h", ","))
	BENCH("list in (1000)", x = ("item999" in L))
	BENCH("assoc lookup", x = assoc["key500"])
	BENCH("list add/remove", L += "z"; L -= "z")
	BENCH("proc call", x = noop(1, 2))
	BENCH("datum proc call", x = T.get())
	BENCH("datum var read", x = T.value)
	BENCH("new/del datum", x = new /datum/thing)
	var/datum/thing/a/b/c/d/e/f/g/D = new
	BENCH("deep datum proc call", x = D.get())
	BENCH("new/del deep datum", x = new /datum/thing/a/b/c/d/e/f/g)
	BENCH("arithmetic", x = (rand(1, 10) * 3 + 7) / 2)
	BENCH("istype", x = istype(T, /datum/thing))
	BENCH("num2text", x = num2text(123.456))

	text2file(jointext(results, "\n"), "results_[ENGINE].txt")
	world.log << "BENCH DONE"
	shutdown()

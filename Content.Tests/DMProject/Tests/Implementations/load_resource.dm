// NOBYOND - implementation smoke test is not a BYOND parity test
/proc/RunTest()
	fdel("load_resource_source.txt")
	text2file("hello", "load_resource_source.txt")

	var/resource = load_resource("load_resource_source.txt")
	ASSERT(isfile(resource))
	ASSERT(fcopy(resource, "load_resource_copy.txt"))
	ASSERT(file2text("load_resource_copy.txt") == "hello\n")

	fdel("load_resource_source.txt")
	fdel("load_resource_copy.txt")

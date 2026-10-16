// text2file appends, writing each call as a line, and file2text sees the new contents straight away
/proc/RunTest()
	fdel("text2file_appends.txt")

	text2file("hello", "text2file_appends.txt")
	ASSERT(file2text("text2file_appends.txt") == "hello\n")

	text2file("b\n", "text2file_appends.txt")
	ASSERT(file2text("text2file_appends.txt") == "hello\nb\n\n")

	fdel("text2file_appends.txt")

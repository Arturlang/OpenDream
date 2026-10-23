"""Compiler fixes self-check: while/do-while with conditions on their own lines, and a proc parameter named args."""


def build(s):
    s.dm("""/proc/ccfix_args(a, args)
	return list(a, args)

/proc/ccfix_while()
	var/n = 0
	var/list/q = list(1)
	while(
		n < 3 \\
		&& length(q)
	)
		n++
	return n

/proc/ccfix_dowhile()
	var/n = 0
	do
		n++
	while(
		n < 4
	)
	return n""")
    s.dm("""/obj/ccfix_thing
	var/car_width = 5

/obj/ccfix_thing/sub
	car_width = 9

/proc/ccfix_loopy()
	var/n = 0
	for(var/i)
		n++
	var/m = 0
	for(var/i)
	m = 7
	return list(n, m)""")
    s.case("initial scope", "list(initial(/obj/ccfix_thing::car_width), initial(/obj/ccfix_thing/sub::car_width), /obj/ccfix_thing/sub::car_width)")
    s.case("for untyped", "ccfix_loopy()")
    s.case("args param", "ccfix_args(1, 7)")
    s.case("args param", "ccfix_args(1)")
    s.case("while multiline", "ccfix_while()")
    s.case("do while multiline", "ccfix_dowhile()")

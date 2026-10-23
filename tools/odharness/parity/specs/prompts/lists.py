"""input() in lists: item kinds and labels, defaults, filters, Cancel, selection position."""
from gen import dm_str as q

DEFS = """
/obj/prompts_x_apple
	name = "apple"

/obj/prompts_x_pear
	name = "pear"

/obj/prompts_x_noname
	name = ""

/obj/prompts_x_improper
	name = "\\improper the thing"

/datum/prompts_x_named
	var/name = "named datum"

/datum/prompts_x_plain

/proc/prompts_x_obj(T)
	return parity_track(new T(locate(1, 1, 1)))
"""

ABC = 'list("alpha", "beta", "gamma")'


def build(s):
    s.prompts()
    s.dm(DEFS)
    p = s.prompt
    sub = [("submit",)]
    sel = lambda i: [("select", i), ("submit",)]

    # Plain text, selection position
    p("list first", f'input(C, "Pick", "List") in {ABC}', sel(0))
    p("list middle", f'input(C, "Pick", "List") in {ABC}', sel(1))
    p("list last", f'input(C, "Pick", "List") in {ABC}', sel(2))
    p("list submit untouched", f'input(C, "Pick", "List") in {ABC}', sub)
    p("list as anything", f'input(C, "Pick", "List") as anything in {ABC}', sel(2))
    p("list usr form", f'input("Pick", "List") in {ABC}', sel(1), lines=["usr = C.mob"])
    p("list unicode items", f'input(C, "Pick", "List") in list({q("äpfel")}, {q("日本")}, {q("☃")})', sel(1))
    p("list empty string item", 'input(C, "Pick", "List") in list("", "b")', sel(0))
    p("list long item", f'input(C, "Pick", "List") in list({q("long " * 30)}, "b")', sel(0))

    # Defaults
    p("list default present", f'input(C, "Pick", "List", "gamma") in {ABC}', sub)
    p("list default absent", f'input(C, "Pick", "List", "delta") in {ABC}', sub)
    p("list default null", f'input(C, "Pick", "List", null) in {ABC}', sub)
    p("list default num in text list", 'input(C, "Pick", "List", 2) in list("1", "2", "3")', sub)
    p("list default text in num list", 'input(C, "Pick", "List", "2") in list(1, 2, 3)', sub)
    p("list default case differs", f'input(C, "Pick", "List", "Beta") in {ABC}', sub)

    # Cancel
    p("null|anything cancel", f'input(C, "Pick", "List") as null|anything in {ABC}', [("press", "Cancel")])
    p("null|anything cancel with default", f'input(C, "Pick", "List", "beta") as null|anything in {ABC}', [("press", "Cancel")])
    p("null|text cancel", f'input(C, "Pick", "List") as null|text in {ABC}', [("press", "Cancel")])
    p("list close", f'input(C, "Pick", "List") as null|anything in {ABC}', [("close",)])

    # Numbers, nulls, duplicates
    p("list numbers", 'input(C, "Pick", "List") in list(1, 2.5, -3, 1e7)', sel(1))
    p("list nulls", 'input(C, "Pick", "List") in list("a", null, "b")', sel(1))
    p("list duplicates", 'input(C, "Pick", "List") in list("a", "b", "a", "b")', sel(2))
    p("list duplicates default", 'input(C, "Pick", "List", "b") in list("a", "b", "a", "b")', sub)

    # Atoms and datums: labels and results
    objs = ['var/obj/A = prompts_x_obj(/obj/prompts_x_apple)', 'var/obj/B = prompts_x_obj(/obj/prompts_x_pear)']
    p("list objs", 'input(C, "Pick", "List") in list(A, B)', sel(1), lines=objs)
    p("list objs default obj", 'input(C, "Pick", "List", B) in list(A, B)', sub, lines=objs)
    p("list objs default name", 'input(C, "Pick", "List", "pear") in list(A, B)', sub, lines=objs)
    p("list same-named objs", 'input(C, "Pick", "List") in list(A, B, D)', sel(2),
      lines=objs + ['var/obj/D = prompts_x_obj(/obj/prompts_x_apple)'])
    p("list obj and text same name", 'input(C, "Pick", "List") in list("apple", A)', sel(1), lines=objs)
    p("list noname obj", 'input(C, "Pick", "List") in list(N, "x")', sel(0),
      lines=['var/obj/N = prompts_x_obj(/obj/prompts_x_noname)'])
    p("list improper obj", 'input(C, "Pick", "List") in list(N, "x")', sel(0),
      lines=['var/obj/N = prompts_x_obj(/obj/prompts_x_improper)'])
    p("list turf", 'input(C, "Pick", "List") in list(locate(1, 1, 1), "x")', sel(0))
    p("list datums", 'input(C, "Pick", "List") in list(new /datum/prompts_x_named, new /datum/prompts_x_plain)', sel(1))
    p("list as obj filter", 'input(C, "Pick", "List") as obj in list("a", A, "b", B)', sel(1), lines=objs)
    p("list paths", 'input(C, "Pick", "List") in list(/obj, /mob, /datum/prompts_x_named)', sel(2))
    p("list nested list", 'input(C, "Pick", "List") in list("a", list(1, 2))', sel(0))

    # Assoc lists
    p("list assoc", 'input(C, "Pick", "List") in list("a" = 1, "b" = 2, "c" = 3)', sel(1))
    p("list assoc default key", 'input(C, "Pick", "List", "c") in list("a" = 1, "b" = 2, "c" = 3)', sub)
    p("list assoc default value", 'input(C, "Pick", "List", 2) in list("a" = 1, "b" = 2, "c" = 3)', sub)
    p("list assoc lookup", 'L[input(C, "Pick", "List") in L]', sel(2), lines=['var/list/L = list("a" = 1, "b" = 2, "c" = 3)'])
    p("list alist", 'input(C, "Pick", "List") in alist("x" = 1, "y" = 2)', sel(1))

    # Sizes
    p("list one item", 'input(C, "Pick", "List") in list("only")', sub)
    p("list one item nullable", 'input(C, "Pick", "List") as null|anything in list("only")', sub)
    p("list empty", 'input(C, "Pick", "List") in list()', [])
    p("list empty nullable", 'input(C, "Pick", "List") as null|anything in list()', [])
    big = ['var/list/L = list()', 'for(var/n in 1 to 50)', '\tL += "item[n]"']
    p("list long last", 'input(C, "Pick", "List") in L', sel(49), lines=big)
    p("list long default", 'input(C, "Pick", "List", "item37") in L', sub, lines=big)

    # Title and message
    p("list empty title message", f'input(C, "", "") in {ABC}', sub)
    p("list multi-line message", f'input(C, {q("one" + chr(10) + "two")}, "List") in {ABC}', sub)

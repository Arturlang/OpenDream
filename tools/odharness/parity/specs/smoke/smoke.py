"""Framework self-check: one case per value kind and hook. Run after changing lib/ or gen.py."""


def build(s):
    s.define("PARITY_MAXX", 12)
    s.dm("/obj/smoke_thing\n\tname = \"thing\"\n\n/proc/smoke_twice(x)\n\treturn x * 2")
    s.case("smoke", "smoke_twice(21)")
    s.case("smoke", "world.maxx")
    s.case("smoke", "matrix(1, 2, 3, 4, 5, 6)")
    s.case("smoke", 'regex("b+")')
    s.body("smoke", ['var/regex/R = regex("b+")', 'R.Find("abbc")'], "R")
    s.case("smoke", "vector(1, 2, 3)")
    s.case("smoke", "new /exception(\"boom\")")
    s.case("smoke", "locate(2, 3, 1)")
    s.case("smoke", "locate(/area)")
    s.body("smoke", ["var/obj/O = parity_track(new /obj/smoke_thing(locate(4, 5, 1)))"], "O")
    # The obj from the case above must be gone
    s.body("smoke", ["var/n = 0", "for(var/obj/smoke_thing/T in world)", "\tn++"], "n")
    s.case("smoke", "icon('test.dmi')")
    s.case("smoke", "icon_states('test.dmi')")
    s.case("smoke", "icon('test.dmi', \"grad\")")
    s.case("smoke", "icon('small.dmi')")
    s.case("smoke", "'test.dmi'")
    s.body("smoke", ['var/icon/I = icon(\'test.dmi\', "asym")'], 'list(I.GetPixel(3, 29), I.GetPixel(1, 1), I.GetPixel(32, 10))')
    s.body("smoke", ['var/icon/I = icon(\'test.dmi\', "dirs4")'], 'list(I.GetPixel(5, 5, "dirs4", SOUTH), I.GetPixel(5, 5, "dirs4", NORTH), I.GetPixel(5, 5, "dirs4", EAST), I.GetPixel(5, 5, "dirs4", WEST))')
    s.body("smoke", ['var/icon/I = icon(\'test.dmi\', "anim")'], 'list(I.GetPixel(5, 5, "anim", 0, 1), I.GetPixel(5, 5, "anim", 0, 2), I.GetPixel(5, 5, "anim", 0, 3))')

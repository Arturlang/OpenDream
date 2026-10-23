"""Render framework self-check: a few cells that should match, one solo page."""


def build(s):
    s.render()
    new = "var/obj/O = parity_track(new /obj(T))"
    s.cell("plain icon", [new, "O.icon = 'test.dmi'", 'O.icon_state = "asym"'])
    s.cell("color red", [new, "O.icon = 'test.dmi'", 'O.icon_state = "grad"', 'O.color = "#ff0000"'])
    s.cell("alpha 128", [new, "O.icon = 'test.dmi'", 'O.icon_state = "solid"', "O.alpha = 128"])
    s.cell("dirs4 east", [new, "O.icon = 'test.dmi'", 'O.icon_state = "dirs4"', "O.dir = EAST"])
    s.cell("turn 45", [new, "O.icon = 'test.dmi'", 'O.icon_state = "asym"', "O.transform = turn(matrix(), 45)"])
    s.cell("scale 2", [new, "O.icon = 'test.dmi'", 'O.icon_state = "asym"', "O.transform = matrix(2, 0, 0, 0, 2, 0)"])
    s.cell("blur 2", [new, "O.icon = 'test.dmi'", 'O.icon_state = "asym"', 'O.filters = filter(type = "blur", size = 2)'])
    s.cell("outline", [new, "O.icon = 'test.dmi'", 'O.icon_state = "half"', 'O.filters = filter(type = "outline", size = 2, color = "#00ffff")'])
    s.cell("drop shadow", [new, "O.icon = 'test.dmi'", 'O.icon_state = "half"', 'O.filters = filter(type = "drop_shadow", x = 4, y = -4, size = 3)'])
    s.cell("pixel offset", [new, "O.icon = 'test.dmi'", 'O.icon_state = "asym"', "O.pixel_x = 17", "O.pixel_y = -9"])
    s.cell("overlay", [new, "O.icon = 'test.dmi'", 'O.icon_state = "half"', 'O.overlays += image(\'small.dmi\', "solid")'])
    s.cell("solo: client color", ["var/obj/O = parity_track(new /obj(T))", "O.icon = 'test.dmi'", 'O.icon_state = "grad"',
                                 'live_client.color = list(0,0,1, 0,1,0, 1,0,0)',
                                 'spawn(30) if(live_client) live_client.color = null'], solo=True)

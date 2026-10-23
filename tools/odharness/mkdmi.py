"""Write a DMI (a PNG plus the BYOND zTXt "Description" chunk) of solid-colour states.

  python -I mkdmi.py out.dmi WxH state=#RRGGBB[AA] [state2=#...]

Each state is one frame, one direction; states are laid out left to right.
"""
import struct, sys, zlib


def chunk(kind, data):
    c = kind + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)


def write_dmi(path, w, h, states):
    width = w * len(states)
    rows = []
    for y in range(h):
        row = bytearray([0])
        for _, (r, g, b, a) in states:
            row += bytes([r, g, b, a]) * w
        rows.append(bytes(row))
    desc = "# BEGIN DMI\nversion = 4.0\n" + f"\twidth = {w}\n\theight = {h}\n"
    for name, _ in states:
        desc += f'state = "{name}"\n\tdirs = 1\n\tframes = 1\n'
    desc += "# END DMI\n"
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, h, 8, 6, 0, 0, 0))
    png += chunk(b"zTXt", b"Description\x00\x00" + zlib.compress(desc.encode()))
    png += chunk(b"IDAT", zlib.compress(b"".join(rows)))
    png += chunk(b"IEND", b"")
    open(path, "wb").write(png)


def parse_color(c):
    c = c.lstrip("#")
    if len(c) == 6:
        c += "ff"
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4, 6))


if __name__ == "__main__":
    out, size, *specs = sys.argv[1:]
    w, h = map(int, size.lower().split("x"))
    write_dmi(out, w, h, [(s.split("=")[0], parse_color(s.split("=")[1])) for s in specs])
    print(f"wrote {out}: {len(specs)} states at {w}x{h}")

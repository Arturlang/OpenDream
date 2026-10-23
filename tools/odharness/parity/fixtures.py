"""Writes the DMI fixtures every parity build gets (parity/fixtures/*.dmi), all made from code so
every pixel is known. Run directly to regenerate: python -I fixtures.py

A state is (name, dirs, frames, delays, fn) where fn(x, y, dir_index, frame) -> (r, g, b, a) with y = 0
at the top row of the PNG. Inside the DMI, a state's images go frame by frame, each frame dir by dir.
"""
import struct, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "fixtures"


def _chunk(kind, data):
    c = kind + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)


def write_dmi(path, w, h, states):
    cells = []
    desc = f"# BEGIN DMI\nversion = 4.0\n\twidth = {w}\n\theight = {h}\n"
    for name, dirs, frames, delays, fn, *extra in states:
        desc += f'state = "{name}"\n\tdirs = {dirs}\n\tframes = {frames}\n'
        if delays:
            desc += "\tdelay = " + ",".join(str(d) for d in delays) + "\n"
        for line in extra:
            desc += f"\t{line}\n"
        for f in range(frames):
            for d in range(dirs):
                cells.append((fn, d, f))
    desc += "# END DMI\n"
    cols = min(len(cells), 8)
    rows_n = (len(cells) + cols - 1) // cols
    W, H = cols * w, rows_n * h
    px = [[(0, 0, 0, 0)] * W for _ in range(H)]
    for i, (fn, d, f) in enumerate(cells):
        ox, oy = (i % cols) * w, (i // cols) * h
        for y in range(h):
            for x in range(w):
                px[oy + y][ox + x] = fn(x, y, d, f)
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in px)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
    png += _chunk(b"zTXt", b"Description\x00\x00" + zlib.compress(desc.encode()))
    png += _chunk(b"IDAT", zlib.compress(raw))
    png += _chunk(b"IEND", b"")
    Path(path).write_bytes(png)


DIR_COLORS = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255),
              (255, 0, 255, 255), (0, 255, 255, 255), (255, 128, 0, 255), (128, 0, 255, 255)]


def asym(x, y, d, f):
    # No symmetry: a marker pixel near the top-left, a bar along the bottom, and a coloured right edge
    if (x, y) == (2, 3):
        return (255, 0, 0, 255)
    if y >= 28 and x < 20:
        return (0, 0, 255, 255)
    if x == 31:
        return (0, 200, 0, 255)
    return (40, 40, 40, 255) if (x + y) % 2 == 0 else (0, 0, 0, 0)


def build():
    OUT.mkdir(exist_ok=True)
    s32 = [
        ("solid", 1, 1, None, lambda x, y, d, f: (200, 30, 30, 255)),
        ("grad", 1, 1, None, lambda x, y, d, f: (x * 8, y * 8, 128, 255)),
        ("alpha", 1, 1, None, lambda x, y, d, f: (255, 255, 255, x * 8)),
        ("half", 1, 1, None, lambda x, y, d, f: (10, 200, 90, 255) if x < 16 else (0, 0, 0, 0)),
        ("checker", 1, 1, None, lambda x, y, d, f: (255, 255, 255, 255) if (x + y) % 2 else (0, 0, 0, 255)),
        ("asym", 1, 1, None, asym),
        ("dirs4", 4, 1, None, lambda x, y, d, f: DIR_COLORS[d] if (x, y) != (1, 1) else (0, 0, 0, 255)),
        ("dirs8", 8, 1, None, lambda x, y, d, f: DIR_COLORS[d]),
        ("anim", 1, 3, [1, 2, 3], lambda x, y, d, f: [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)][f]),
        ("anim4", 4, 2, [2, 2], lambda x, y, d, f: tuple(min(255, c + 60 * f) for c in DIR_COLORS[d][:3]) + (255,)),
        ("rewind", 1, 2, [1, 1], lambda x, y, d, f: (f * 255, 0, 0, 255), "rewind = 1"),
        ("moving", 1, 1, None, lambda x, y, d, f: (1, 2, 3, 255), "movement = 1"),
        ("", 1, 1, None, lambda x, y, d, f: (9, 9, 9, 255)),
        ("empty", 1, 1, None, lambda x, y, d, f: (0, 0, 0, 0)),
    ]
    write_dmi(OUT / "test.dmi", 32, 32, s32)
    write_dmi(OUT / "small.dmi", 16, 16, [
        ("solid", 1, 1, None, lambda x, y, d, f: (0, 0, 255, 255)),
        ("grad", 1, 1, None, lambda x, y, d, f: (x * 16, y * 16, 0, 255)),
    ])
    # Render pages: a two-grey 8px checker background (shows alpha and blending), pure magenta corner
    # markers the comparer locates the map by, and a white tile coloured per page to prove which page is shown
    write_dmi(OUT / "render.dmi", 32, 32, [
        ("bg", 1, 1, None, lambda x, y, d, f: (96, 96, 96, 255) if ((x // 8) + (y // 8)) % 2 else (160, 160, 160, 255)),
        ("marker", 1, 1, None, lambda x, y, d, f: (255, 0, 255, 255)),
        ("code", 1, 1, None, lambda x, y, d, f: (255, 255, 255, 255)),
    ])
    write_dmi(OUT / "rect.dmi", 32, 16, [
        ("wide", 1, 1, None, lambda x, y, d, f: (x * 8, 0, y * 16, 255)),
    ])
    return sorted(OUT.glob("*.dmi"))


if __name__ == "__main__":
    for f in build():
        print(f)

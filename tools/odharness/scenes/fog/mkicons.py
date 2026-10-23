"""Generate the fog scene's icons: animated static, soft reveal disk, soft LOS marker, plain tiles.

    python -I mkicons.py
"""
import os
import random
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TILE = 32
REVEAL_RADIUS = 7.5 * TILE
REVEAL_FEATHER = 2 * TILE
MARKER_SIZE = 64
MARKER_FEATHER = 16


def chunk(kind, data):
    c = kind + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)


def write_dmi(path, w, h, states):
    """states: list of (name, [frame_pixels...], delays or None); frame_pixels is a list of h rows of w RGBA tuples"""
    frames = [(name, f) for name, fl, _ in states for f in fl]
    width = w * len(frames)
    rows = []
    for y in range(h):
        row = bytearray([0])
        for _, f in frames:
            for px in f[y]:
                row += bytes(px)
        rows.append(bytes(row))
    desc = "# BEGIN DMI\nversion = 4.0\n" + f"\twidth = {w}\n\theight = {h}\n"
    for name, fl, delays in states:
        desc += f'state = "{name}"\n\tdirs = 1\n\tframes = {len(fl)}\n'
        if delays:
            desc += "\tdelay = " + ",".join(str(d) for d in delays) + "\n"
    desc += "# END DMI\n"
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, h, 8, 6, 0, 0, 0))
    png += chunk(b"zTXt", b"Description\x00\x00" + zlib.compress(desc.encode()))
    png += chunk(b"IDAT", zlib.compress(b"".join(rows)))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def solid(w, h, rgba):
    return [[rgba] * w for _ in range(h)]


def static_frame(rng):
    rows = []
    for _ in range(TILE):
        row = []
        for _ in range(TILE):
            v = rng.randint(20, 110)
            row.append((v, v, v + 10, 255))
        rows.append(row)
    return rows


def smoothstep(edge0, edge1, x):
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)


def reveal_disk():
    size = int(REVEAL_RADIUS * 2)
    c = size / 2
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            d = ((x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2) ** 0.5
            a = int(255 * (1 - smoothstep(REVEAL_RADIUS - REVEAL_FEATHER, REVEAL_RADIUS, d)))
            row.append((255, 255, 255, a))
        rows.append(row)
    return size, rows


def soft_marker():
    rows = []
    for y in range(MARKER_SIZE):
        row = []
        for x in range(MARKER_SIZE):
            edge = min(x + 0.5, y + 0.5, MARKER_SIZE - x - 0.5, MARKER_SIZE - y - 0.5)
            a = int(255 * smoothstep(0, 2 * MARKER_FEATHER, edge))
            row.append((255, 255, 255, a))
        rows.append(row)
    return rows


def main():
    rng = random.Random(1)
    write_dmi(os.path.join(HERE, "static.dmi"), TILE, TILE,
              [("static", [static_frame(rng) for _ in range(4)], [1, 1, 1, 1])])
    size, disk = reveal_disk()
    write_dmi(os.path.join(HERE, "reveal.dmi"), size, size, [("reveal", [disk], None)])
    write_dmi(os.path.join(HERE, "marker.dmi"), MARKER_SIZE, MARKER_SIZE, [("marker", [soft_marker()], None)])
    write_dmi(os.path.join(HERE, "tiles.dmi"), TILE, TILE, [
        ("floor", [solid(TILE, TILE, (70, 80, 72, 255))], None),
        ("wall", [solid(TILE, TILE, (150, 150, 160, 255))], None),
        ("door_closed", [solid(TILE, TILE, (170, 120, 60, 255))], None),
        ("door_open", [solid(TILE, TILE, (90, 70, 40, 255))], None),
        ("marine", [solid(TILE, TILE, (60, 140, 255, 255))], None),
        ("tile_static", [static_frame(rng) for _ in range(4)], [1, 1, 1, 1]),
    ])
    print("icons written to", HERE)


if __name__ == "__main__":
    main()

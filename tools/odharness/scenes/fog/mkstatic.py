"""Generate camera static candidates (seamless, animated) plus previews.

    python -I mkstatic.py <tgmc_repo>

Writes static_candidates/<name>.dmi, <name>_tiled.png (frame 0 tiled 3x3) and <name>.gif (animated, 2x2 tiles),
plus current_tgmc_tiled.png (TGMC's cameravis.dmi tiled over the same area) for comparison.
"""
import os
import sys
import struct
import zlib

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "static_candidates")
SIZE = 256
FRAMES = 8
rng = np.random.default_rng(7)


def chunk(kind, data):
    c = kind + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)


def write_dmi(path, frames, state=""):
    """frames: list of HxWx4 uint8 arrays, laid out left to right as one animated state"""
    h, w = frames[0].shape[:2]
    sheet = np.concatenate(frames, axis=1)
    rows = b"".join(b"\x00" + sheet[y].tobytes() for y in range(h))
    desc = "# BEGIN DMI\nversion = 4.0\n" + f"\twidth = {w}\n\theight = {h}\n"
    desc += f'state = "{state}"\n\tdirs = 1\n\tframes = {len(frames)}\n\tdelay = ' + ",".join(["1"] * len(frames)) + "\n"
    desc += "# END DMI\n"
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", sheet.shape[1], h, 8, 6, 0, 0, 0))
    png += chunk(b"zTXt", b"Description\x00\x00" + zlib.compress(desc.encode()))
    png += chunk(b"IDAT", zlib.compress(rows))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def wrap_blur(a, radius):
    """Box blur that wraps around the edges, so the result stays seamless"""
    out = a.astype(np.float32)
    for axis in (0, 1):
        acc = np.zeros_like(out)
        for d in range(-radius, radius + 1):
            acc += np.roll(out, d, axis=axis)
        out = acc / (2 * radius + 1)
    return out


def colorize(value):
    """value 0..1 -> blue-grey static matching TGMC's cameravis tone"""
    v = np.clip(value, 0, 1)
    r = 30 + v * 120
    g = 34 + v * 124
    b = 44 + v * 140
    a = np.full_like(v, 255)
    return np.stack([r, g, b, a], axis=-1).astype(np.uint8)


def fine_grain():
    frames = []
    for _ in range(FRAMES):
        n = rng.random((SIZE // 2, SIZE // 2))
        n = np.kron(n, np.ones((2, 2)))
        frames.append(colorize(n * 0.85 + 0.075))
    return frames


def tv_static():
    frames = []
    bands = rng.random(SIZE)
    bands = wrap_blur(np.tile(bands[:, None], (1, 4)), 6)[:, 0]
    for f in range(FRAMES):
        n = rng.random((SIZE, SIZE))
        roll = np.roll(bands, f * SIZE // FRAMES)
        shade = 0.55 + 0.45 * (roll - roll.min()) / (roll.max() - roll.min() + 1e-6)
        scan = np.where(np.arange(SIZE) % 2 == 0, 1.0, 0.8)
        frames.append(colorize(n * shade[:, None] * scan[:, None]))
    return frames


def soft_fog():
    base = wrap_blur(rng.random((SIZE, SIZE)), 10)
    base = (base - base.min()) / (base.max() - base.min())
    frames = []
    for _ in range(FRAMES):
        grain = rng.random((SIZE, SIZE))
        frames.append(colorize(0.35 * base + 0.55 * grain + 0.05))
    return frames


def preview(name, frames):
    tile = Image.fromarray(frames[0])
    big = Image.new("RGBA", (SIZE * 3, SIZE * 3))
    for x in range(3):
        for y in range(3):
            big.paste(tile, (x * SIZE, y * SIZE))
    big.save(os.path.join(OUT, f"{name}_tiled.png"))
    anim = []
    for f in frames:
        t = Image.fromarray(f)
        a = Image.new("RGBA", (SIZE * 2, SIZE * 2))
        for x in range(2):
            for y in range(2):
                a.paste(t, (x * SIZE, y * SIZE))
        anim.append(a.convert("RGB"))
    anim[0].save(os.path.join(OUT, f"{name}.gif"), save_all=True, append_images=anim[1:], duration=100, loop=0)


def current_tgmc(repo):
    im = Image.open(os.path.join(repo, "icons", "effects", "cameravis.dmi")).convert("RGBA")
    frame = im.crop((0, 0, 32, 32))
    big = Image.new("RGBA", (SIZE * 3, SIZE * 3))
    for x in range(0, SIZE * 3, 32):
        for y in range(0, SIZE * 3, 32):
            big.paste(frame, (x, y))
    big.save(os.path.join(OUT, "current_tgmc_tiled.png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, gen in (("fine_grain", fine_grain), ("tv_static", tv_static), ("soft_fog", soft_fog)):
        frames = gen()
        write_dmi(os.path.join(OUT, f"{name}.dmi"), frames)
        preview(name, frames)
    if len(sys.argv) > 1:
        current_tgmc(sys.argv[1])
    print("written to", OUT)


if __name__ == "__main__":
    main()

"""Decode DMIs: print their metadata and render every frame of each, scaled, into one comparison PNG.
  python -I dmiview.py out.png a.dmi [b.dmi ...]
"""
import struct, sys, zlib

def read_png(path):
    b = open(path, 'rb').read(); i = 8; idat = b''; desc = ''
    while i < len(b):
        n = struct.unpack('>I', b[i:i+4])[0]; t = b[i+4:i+8]; d = b[i+8:i+8+n]
        if t == b'IHDR': w, h, bd, ct = struct.unpack('>IIBB', d[:10])
        elif t == b'IDAT': idat += d
        elif t == b'zTXt': k = d.index(b'\0'); desc = zlib.decompress(d[k+2:]).decode()
        elif t == b'tEXt': k = d.index(b'\0'); desc = d[k+1:].decode(errors='replace')
        elif t == b'PLTE': plte = d
        elif t == b'tRNS': trns = d
        i += 12 + n
    raw = zlib.decompress(idat)
    bpp = {6: 4, 2: 3, 3: 1, 0: 1, 4: 2}[ct]
    if bd != 8 and ct not in (3, 0): raise SystemExit(f'{path}: bit depth {bd} unsupported')
    stride = w * bpp if bd == 8 else (w * bd + 7) // 8; rows = []; prev = bytearray(stride)
    for y in range(h):
        f = raw[y*(stride+1)]; line = bytearray(raw[y*(stride+1)+1:(y+1)*(stride+1)])
        for x in range(stride):
            a = line[x-bpp] if x >= bpp else 0; up = prev[x]; c = prev[x-bpp] if x >= bpp else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + up) & 255
            elif f == 3: line[x] = (line[x] + (a + up) // 2) & 255
            elif f == 4:
                p = a + up - c; pa, pb, pc = abs(p-a), abs(p-up), abs(p-c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else up if pb <= pc else c)) & 255
        prev = line
        if bd < 8:  # unpack sub-byte palette indices to one byte per pixel
            per = 8 // bd; mask = (1 << bd) - 1
            line = bytearray(((line[i // per] >> (8 - bd * (i % per + 1))) & mask) for i in range(w))
        rows.append(line)
    def px(x, y):
        r = rows[y]
        if ct == 6: return tuple(r[x*4:x*4+4])
        if ct == 2: return (*r[x*3:x*3+3], 255)
        if ct == 3:
            idx = r[x]; rgb = plte[idx*3:idx*3+3]; al = trns[idx] if 'trns' in dir() and idx < len(trns) else 255
            return (*rgb, al)
        if ct == 0: return (r[x], r[x], r[x], 255)
        if ct == 4: return (r[x*2], r[x*2], r[x*2], r[x*2+1])
    if ct == 3:
        nonlocal_trns = locals().get('trns', b'')
        def px(x, y, rows=rows, plte=plte, trns=nonlocal_trns):
            idx = rows[y][x]; rgb = plte[idx*3:idx*3+3]
            return (*rgb, trns[idx] if idx < len(trns) else 255)
    return w, h, desc, px, ct

def write_png(path, w, h, pixels):
    raw = b''.join(b'\0' + bytes(c for p in pixels[y*w:(y+1)*w] for c in p) for y in range(h))
    def chunk(t, d): c = t + d; return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))

out, files = sys.argv[1], sys.argv[2:]
S = 4; frames_all = []
for f in files:
    w, h, desc, px, ct = read_png(f)
    fw = int(desc.split('width = ')[1].split()[0]) if 'width =' in desc else w
    fh = int(desc.split('height = ')[1].split()[0]) if 'height =' in desc else h
    print(f'== {f}: png {w}x{h} colortype {ct}, frame {fw}x{fh}\n{desc.strip()}')
    frames = []
    for fy in range(h // fh):
        for fx in range(w // fw):
            frames.append([[px(fx*fw+x, fy*fh+y) for x in range(fw)] for y in range(fh)])
    frames_all.append((fw, fh, frames))
cols = max(len(fr) for _, _, fr in frames_all); fw = max(f[0] for f in frames_all); fh = max(f[1] for f in frames_all)
W, H = cols * (fw*S + 4), len(frames_all) * (fh*S + 4)
img = [(255, 0, 255, 255)] * (W * H)
for row, (w_, h_, frames) in enumerate(frames_all):
    for col, fr in enumerate(frames):
        for y in range(h_):
            for x in range(w_):
                r, g, b, a = fr[y][x]
                # composite over a mid grey so transparency and white both show
                bg = 90; c = (r*a + bg*(255-a)) // 255, (g*a + bg*(255-a)) // 255, (b*a + bg*(255-a)) // 255
                for dy in range(S):
                    for dx in range(S):
                        img[(row*(fh*S+4) + y*S + dy) * W + col*(fw*S+4) + x*S + dx] = (*c, 255)
write_png(out, W, H, img)
print('wrote', out)

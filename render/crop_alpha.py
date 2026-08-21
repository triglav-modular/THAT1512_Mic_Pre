#!/usr/bin/env python3
"""Crop a transparent PNG to its visible content plus an even margin.

Cycles renders into a fixed square; the board plus its shadow occupies an arbitrary
sub-rectangle of that. Run this after render.sh to tighten the framing.

Usage: crop_alpha.py in.png out.png [alpha_threshold] [pad_px]
"""
import sys, zlib, struct


def read(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', "not a PNG"
    i, idat = 8, b''
    w = h = bd = ct = None
    while i < len(d):
        ln = struct.unpack('>I', d[i:i + 4])[0]
        typ = d[i + 4:i + 8]
        data = d[i + 8:i + 8 + ln]
        i += 12 + ln
        if typ == b'IHDR':
            w, h, bd, ct, _, _, il = struct.unpack('>IIBBBBB', data)
            assert il == 0 and bd == 8 and ct == 6, "need 8-bit RGBA, non-interlaced"
        elif typ == b'IDAT':
            idat += data
        elif typ == b'IEND':
            break
    raw = zlib.decompress(idat)
    stride = w * 4
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        f = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos + stride]); pos += stride
        for x in range(stride):
            a = line[x - 4] if x >= 4 else 0
            b = prev[x]
            c = prev[x - 4] if x >= 4 else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out += line
        prev = line
    return w, h, bytes(out)


def write(path, w, h, px):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += px[y * w * 4:(y + 1) * w * 4]

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)

    open(path, 'wb').write(
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
        + chunk(b'IEND', b''))


def main():
    src, dst = sys.argv[1], sys.argv[2]
    thr = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    pad = int(sys.argv[4]) if len(sys.argv) > 4 else 40
    w, h, px = read(src)
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        row = px[y * w * 4:(y + 1) * w * 4]
        for x in range(w):
            if row[x * 4 + 3] > thr:
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
    if x1 < 0:
        print("nothing visible above threshold"); sys.exit(1)
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(w - 1, x1 + pad); y1 = min(h - 1, y1 + pad)
    nw, nh = x1 - x0 + 1, y1 - y0 + 1
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        s = ((y + y0) * w + x0) * 4
        out[y * nw * 4:(y + 1) * nw * 4] = px[s:s + nw * 4]
    write(dst, nw, nh, bytes(out))
    print(f"{w}x{h} -> {nw}x{nh}")


if __name__ == '__main__':
    main()

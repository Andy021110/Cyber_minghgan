"""
scripts/make_transparent_pet.py — 把角色图抠成透明底，供桌宠使用

为什么需要它：npc_cyber_v*.png 都没有透明通道（实测三个版本 alpha 全为 255），
直接用会显示成一个青色方块，完全不是"浮在桌面上"的效果。

做法：色度键——把背景/边框的青色系设为透明，保留角色本体（灰白系）。
**只读原图，输出新文件，绝不修改原图。**

用法：
    .venv/bin/python scripts/make_transparent_pet.py [v1|v2|v3]
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

# 被判为背景（将变透明）的颜色——这些是边框与底色
CHROMA_KEYS = {
    (0, 172, 193),    # 深青：四角与边框
    (77, 208, 225),   # 浅青：底色（占 52%）
}


def decode_png(path: Path):
    """最小 PNG 解码（8bit、非隔行）。"""
    d = path.read_bytes()
    pos, w, h, idat, ct = 8, 0, 0, b"", 0
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        data = d[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, _bd, ct = struct.unpack(">IIBB", data[:10])
        elif typ == b"IDAT":
            idat += data
        elif typ == b"IEND":
            break
        pos += 12 + ln
    raw = zlib.decompress(idat)
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    stride = w * ch
    out, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f = raw[i]; i += 1
        line = bytearray(raw[i:i + stride]); i += stride
        for x in range(stride):
            a = line[x - ch] if x >= ch else 0
            b = prev[x]
            c = prev[x - ch] if x >= ch else 0
            if f == 1:   line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out.append(bytes(line)); prev = line
    return w, h, ch, out


def encode_png_rgba(path: Path, w: int, h: int, rows: list[bytes]) -> None:
    """最小 PNG 编码（RGBA、filter=0）。"""
    def chunk(typ: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    body = b"".join(b"\x00" + r for r in rows)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(body, 9))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    ver = sys.argv[1] if len(sys.argv) > 1 else "v2"
    src = Path(f"frontend/public/assets/npc_cyber_{ver}.png")
    if not src.exists():
        print(f"找不到源文件：{src}")
        return 1

    w, h, ch, rows = decode_png(src)
    out_rows, removed = [], 0
    total = w * h
    for y in range(h):
        r, line = rows[y], bytearray()
        for x in range(w):
            px = (r[x * ch], r[x * ch + 1], r[x * ch + 2])
            if px in CHROMA_KEYS:
                line += b"\x00\x00\x00\x00"      # 背景 → 全透明
                removed += 1
            else:
                line += bytes([px[0], px[1], px[2], 255])
        out_rows.append(bytes(line))

    dst = Path(f"desktop/src/pet/assets/pet_{ver}.png")
    dst.parent.mkdir(parents=True, exist_ok=True)
    encode_png_rgba(dst, w, h, out_rows)

    print(f"源图     : {src}  ({w}x{h})")
    print(f"抠掉背景 : {removed * 100 // total}%")
    print(f"输出     : {dst}")
    print(f"原图未改动 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

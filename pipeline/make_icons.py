"""홈 화면용 PNG 아이콘(192, 512)을 외부 라이브러리 없이 그린다.

사용법:
    python -I pipeline/make_icons.py site
"""
import struct
import sys
import zlib
from pathlib import Path

BG = (0x2E, 0x6B, 0x4A)
LEAF = (0xE0, 0xED, 0xE4)
LEAF2 = (0xB9, 0xDC, 0xC4)


def in_leaf(x, y, cx, cy, r, flip):
    # 두 원이 겹친 렌즈 모양 잎
    d = r * 0.55
    ax, ay = (cx - d, cy + d) if not flip else (cx + d, cy + d)
    bx, by = (cx + d, cy - d) if not flip else (cx - d, cy - d)
    return (x - ax) ** 2 + (y - ay) ** 2 < r * r and (x - bx) ** 2 + (y - by) ** 2 < r * r


def draw(size):
    s = size / 64
    rows = []
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            x, y = px / s, py / s
            c = BG
            if abs(x - 32) < 1.6 and 21 < y < 52:
                c = LEAF
            if in_leaf(x, y, 24, 25, 11, False):
                c = LEAF
            if in_leaf(x, y, 40, 31, 11, True):
                c = LEAF2
            row += bytes(c)
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    out = Path(sys.argv[1])
    for size in (192, 512):
        (out / f"icon-{size}.png").write_bytes(draw(size))
        print(f"icon-{size}.png")

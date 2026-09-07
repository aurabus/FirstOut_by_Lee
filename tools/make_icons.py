"""홈 화면 아이콘을 그린다 — 이미지 라이브러리 없이.

선생님 폰 홈 화면에 놓일 그림이라 작게 줄여도 알아볼 수 있어야 한다.
두 사람이 손을 잡고 선 모습 — 「손잡고 마중」 그대로다.

    python tools/make_icons.py

Pillow 를 쓰지 않는 이유는 설치 환경을 하나라도 줄이기 위해서다.
계단 현상을 없애려고 네 배로 그린 뒤 줄인다.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "firstout" / "static"

PINE = (10, 107, 85)        # #0A6B55 — 브랜드 색
WHITE = (255, 255, 255)
SS = 4                      # 네 배로 그린 뒤 줄인다


def _rounded(x: float, y: float, x0: float, y0: float, x1: float, y1: float, r: float) -> bool:
    """모서리가 둥근 네모 안에 있는가."""
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _circle(x: float, y: float, cx: float, cy: float, r: float) -> bool:
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def draw(size: int) -> bytes:
    """RGB 픽셀을 만든다."""
    n = size * SS
    s = float(n)
    rows = []
    for py in range(n):
        row = bytearray()
        for px in range(n):
            x, y = px + 0.5, py + 0.5
            on_bg = _rounded(x, y, 0, 0, s, s, s * 0.22)
            if not on_bg:
                row += bytes((255, 255, 255))     # 바깥은 흰색 (둥근 모서리)
                continue

            mark = (
                # 어른 — 키가 크다
                _circle(x, y, s * 0.345, s * 0.235, s * 0.105)
                or _rounded(x, y, s * 0.245, s * 0.375, s * 0.445, s * 0.855, s * 0.10)
                # 아이 — 작다. 크기를 다르게 해야 「어른과 아이」로 읽힌다
                or _circle(x, y, s * 0.685, s * 0.435, s * 0.082)
                or _rounded(x, y, s * 0.605, s * 0.545, s * 0.765, s * 0.855, s * 0.08)
                # 맞잡은 손
                or _rounded(x, y, s * 0.425, s * 0.625, s * 0.625, s * 0.685, s * 0.03)
            )
            row += bytes(WHITE if mark else PINE)
        rows.append(bytes(row))

    return _shrink(rows, n, size)


def _shrink(rows: list[bytes], n: int, size: int) -> bytes:
    """네 배 그림을 평균 내어 줄인다 — 가장자리가 부드러워진다."""
    out = bytearray()
    for oy in range(size):
        line = bytearray(b"\x00")          # PNG 줄머리 (필터 없음)
        for ox in range(size):
            r = g = b = 0
            for dy in range(SS):
                src = rows[oy * SS + dy]
                base = (ox * SS) * 3
                for dx in range(SS):
                    i = base + dx * 3
                    r += src[i]
                    g += src[i + 1]
                    b += src[i + 2]
            k = SS * SS
            line += bytes((r // k, g // k, b // k))
        out += line
    return bytes(out)


def png(size: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    head = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)   # 8비트 RGB
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", head)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def main() -> None:
    for name, size in (("icon-192.png", 192), ("icon-512.png", 512),
                       ("apple-touch-icon.png", 180)):
        (OUT / name).write_bytes(png(size, draw(size)))
        print(f"  {name} ({size}×{size})")


if __name__ == "__main__":
    main()

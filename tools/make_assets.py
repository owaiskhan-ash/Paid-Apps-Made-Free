#!/usr/bin/env python3
"""Generate the social share image and touch icon for the App 01 landing page.

Pure standard library: geometry is rasterised by hand with analytic
anti-aliasing and the PNGs are written with zlib. No fonts are used, so the
artwork stays purely geometric: fluorescent field, hairline grid, thin "01".

Run from the repository root:

    python3 tools/make_assets.py
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

FLUORO = (0xCC, 0xFF, 0x00)
INK = (0x0B, 0x0B, 0x0B)


class Canvas:
    def __init__(self, width: int, height: int, color: tuple[int, int, int]) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(bytes(color) * (width * height))

    def _blend(self, x: int, y: int, coverage: float, color: tuple[int, int, int]) -> None:
        if coverage <= 0 or not (0 <= x < self.width and 0 <= y < self.height):
            return
        if coverage > 1:
            coverage = 1.0
        index = (y * self.width + x) * 3
        for channel in range(3):
            base = self.pixels[index + channel]
            self.pixels[index + channel] = round(
                base + (color[channel] - base) * coverage
            )

    def segment(self, x1, y1, x2, y2, width=1.0, alpha=1.0, color=INK) -> None:
        half = width / 2
        reach = half + 1
        min_x = max(int(math.floor(min(x1, x2) - reach)), 0)
        max_x = min(int(math.ceil(max(x1, x2) + reach)), self.width - 1)
        min_y = max(int(math.floor(min(y1, y2) - reach)), 0)
        max_y = min(int(math.ceil(max(y1, y2) + reach)), self.height - 1)
        dx, dy = x2 - x1, y2 - y1
        length_sq = dx * dx + dy * dy
        for y in range(min_y, max_y + 1):
            py = y + 0.5
            for x in range(min_x, max_x + 1):
                px = x + 0.5
                if length_sq:
                    t = ((px - x1) * dx + (py - y1) * dy) / length_sq
                    t = 0.0 if t < 0 else 1.0 if t > 1 else t
                else:
                    t = 0.0
                distance = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
                coverage = (half + 0.5 - distance) * alpha
                if coverage > 0:
                    self._blend(x, y, coverage, color)

    def ring(self, cx, cy, rx, ry, width=1.0, alpha=1.0, color=INK) -> None:
        """Ellipse outline with an even stroke weight all the way round."""
        half = width / 2
        min_x = max(int(math.floor(cx - rx - half - 1)), 0)
        max_x = min(int(math.ceil(cx + rx + half + 1)), self.width - 1)
        min_y = max(int(math.floor(cy - ry - half - 1)), 0)
        max_y = min(int(math.ceil(cy + ry + half + 1)), self.height - 1)
        for y in range(min_y, max_y + 1):
            dy = y + 0.5 - cy
            for x in range(min_x, max_x + 1):
                dx = x + 0.5 - cx
                scaled = math.hypot(dx / rx, dy / ry)
                gradient = math.hypot(dx / (rx * rx), dy / (ry * ry))
                if gradient == 0:
                    distance = min(rx, ry)
                else:
                    distance = abs(scaled - 1.0) * scaled / gradient
                coverage = (half + 0.5 - distance) * alpha
                if coverage > 0:
                    self._blend(x, y, coverage, color)

    def to_png(self) -> bytes:
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            raw.extend(self.pixels[y * stride : (y + 1) * stride])

        def chunk(tag: bytes, payload: bytes) -> bytes:
            return (
                struct.pack(">I", len(payload))
                + tag
                + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
            )

        header = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b"")
        )


def draw_grid(canvas: Canvas, inset: int) -> None:
    """Hairline frame plus the two vertical rules and the centre rule."""
    w, h = canvas.width, canvas.height
    soft = 0.16
    stroke = max(canvas.width / 1200, 1.0)

    canvas.segment(inset, inset, w - inset, inset, stroke, 0.5)
    canvas.segment(inset, h - inset, w - inset, h - inset, stroke, 0.5)
    canvas.segment(inset, inset, inset, h - inset, stroke, 0.5)
    canvas.segment(w - inset, inset, w - inset, h - inset, stroke, 0.5)

    canvas.segment(w * 0.22, inset, w * 0.22, h - inset, stroke, soft)
    canvas.segment(w * 0.78, inset, w * 0.78, h - inset, stroke, soft)
    canvas.segment(inset, h * 0.5, w - inset, h * 0.5, stroke, soft)


def draw_unit(canvas: Canvas, cx: float, cy: float, box: float, stroke: float) -> None:
    """A thin geometric '01' inside a square box of the given size."""
    zero_rx = box * 0.19
    zero_ry = box * 0.5
    zero_cx = cx - box * 0.17
    canvas.ring(zero_cx, cy, zero_rx, zero_ry, stroke)

    one_x = cx + box * 0.2
    canvas.segment(one_x, cy - box * 0.5, one_x, cy + box * 0.5, stroke)
    canvas.segment(one_x, cy - box * 0.5, one_x - box * 0.17, cy - box * 0.34, stroke)
    canvas.segment(one_x - box * 0.13, cy + box * 0.5, one_x + box * 0.13, cy + box * 0.5, stroke)


def build_og() -> bytes:
    canvas = Canvas(1200, 630, FLUORO)
    draw_grid(canvas, 40)
    draw_unit(canvas, 600, 315, 250, 4.0)
    canvas.segment(64, 68, 78, 68, 1.0, 0.85)
    canvas.segment(64, 68, 64, 82, 1.0, 0.85)
    canvas.segment(64, 562, 78, 562, 1.0, 0.45)
    canvas.segment(64, 548, 64, 562, 1.0, 0.45)
    return canvas.to_png()


def build_icon() -> bytes:
    canvas = Canvas(180, 180, FLUORO)
    draw_grid(canvas, 16)
    draw_unit(canvas, 90, 90, 74, 2.0)
    return canvas.to_png()


BRAND_MARK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-labelledby="title">
  <title id="title">App 01 mark</title>
  <rect width="512" height="512" fill="#ccff00"/>
  <rect x="24.5" y="24.5" width="463" height="463" fill="none" stroke="#0b0b0b" stroke-opacity=".5" stroke-width="1"/>
  <ellipse cx="226" cy="256" rx="58" ry="152" fill="none" stroke="#0b0b0b" stroke-width="8"/>
  <path d="M318 104v304M318 104l-52 41M278 408h80" fill="none" stroke="#0b0b0b" stroke-width="8"/>
</svg>
"""


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "og-image.png").write_bytes(build_og())
    (ASSETS / "apple-touch-icon.png").write_bytes(build_icon())
    (ASSETS / "brand-mark.svg").write_text(BRAND_MARK, encoding="utf-8")
    print("wrote assets/og-image.png, assets/apple-touch-icon.png, assets/brand-mark.svg")


if __name__ == "__main__":
    main()

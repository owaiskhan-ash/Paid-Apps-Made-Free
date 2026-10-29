#!/usr/bin/env python3
"""Refresh derived favicon sizes from assets/free-app-icon.png and verify share assets.

Run from the repository root:

    python3 tools/make_assets.py
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SOURCE_ICON = ASSETS / "free-app-icon.png"
OG_IMAGE = ASSETS / "og-image.png"

DERIVED_PNGS = {
    ASSETS / "favicon-16x16.png": 16,
    ASSETS / "favicon-32x32.png": 32,
    ASSETS / "favicon-48x48.png": 48,
    ASSETS / "favicon-96x96.png": 96,
    ASSETS / "apple-touch-icon.png": 180,
    ROOT / "apple-touch-icon.png": 180,
    ASSETS / "icon-192x192.png": 192,
    ROOT / "favicon.png": 192,
    ASSETS / "icon-512x512.png": 512,
}


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"{path} is not a valid PNG file")
    return struct.unpack(">II", header[16:24])


def main() -> None:
    if not SOURCE_ICON.exists():
        raise FileNotFoundError(f"Missing source icon: {SOURCE_ICON}")
    if not OG_IMAGE.exists():
        raise FileNotFoundError(f"Missing Open Graph share card: {OG_IMAGE}")

    convert = shutil.which("convert")
    if convert:
        for dest, size in DERIVED_PNGS.items():
            subprocess.run(
                [
                    convert,
                    str(SOURCE_ICON),
                    "-filter",
                    "Lanczos",
                    "-resize",
                    f"{size}x{size}",
                    "-strip",
                    f"PNG24:{dest}",
                ],
                check=True,
            )
        subprocess.run(
            [
                convert,
                str(SOURCE_ICON),
                "-define",
                "icon:auto-resize=96,48,32,16",
                "-strip",
                str(ROOT / "favicon.ico"),
            ],
            check=True,
        )

    og_size = png_dimensions(OG_IMAGE)
    for dest, size in DERIVED_PNGS.items():
        actual = png_dimensions(dest)
        if actual != (size, size):
            raise RuntimeError(f"Expected {dest} to be {(size, size)}, got {actual}")
    print(f"verified og-image.png={og_size} and {len(DERIVED_PNGS)} derived icons + favicon.ico")


if __name__ == "__main__":
    main()

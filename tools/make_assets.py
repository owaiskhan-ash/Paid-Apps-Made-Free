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
        subprocess.run(
            [
                convert,
                str(SOURCE_ICON),
                "-filter",
                "Lanczos",
                "-resize",
                "180x180",
                "-strip",
                f"PNG24:{ASSETS / 'apple-touch-icon.png'}",
            ],
            check=True,
        )
        subprocess.run(
            [
                convert,
                str(SOURCE_ICON),
                "-filter",
                "Lanczos",
                "-resize",
                "32x32",
                "-strip",
                f"PNG24:{ASSETS / 'favicon-32x32.png'}",
            ],
            check=True,
        )
        subprocess.run(
            [
                convert,
                str(SOURCE_ICON),
                "-define",
                "icon:auto-resize=48,32,16",
                "-strip",
                str(ROOT / "favicon.ico"),
            ],
            check=True,
        )

    og_size = png_dimensions(OG_IMAGE)
    touch_size = png_dimensions(ASSETS / "apple-touch-icon.png")
    fav_size = png_dimensions(ASSETS / "favicon-32x32.png")
    print(f"verified og-image.png={og_size}, apple-touch-icon.png={touch_size}, favicon-32x32.png={fav_size}")


if __name__ == "__main__":
    main()

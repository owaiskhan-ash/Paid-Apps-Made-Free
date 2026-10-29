#!/usr/bin/env python3
"""Keep the download button pointed at the newest AutoWall release.

GitHub's ``/releases/latest/download/<asset>`` alias already redirects to the
newest published release, so the button never downloads an old build. Two
things can still drift, though, and this script fixes both:

1. the *asset file name* — if a release renames the APK, the alias 404s;
2. the visible version caption — it says whatever was current when the page
   was last edited.

It reads the GitHub release API, picks the installable APK, then rewrites
``index.html`` (download button, release-notes button, JSON-LD, caption) so
everything names the same, currently-latest release.

Usage, from the repository root:

    python3 tools/sync_release.py           # update index.html
    python3 tools/sync_release.py --check    # exit 1 if it is out of date
    python3 tools/sync_release.py --offline  # report the pinned values only

Set ``GITHUB_TOKEN`` when running in CI to avoid the anonymous rate limit.
Standard library only; no dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "index.html"

OWNER = "owaiskhan-ash"
REPO = "Automatic-wallpaper-changer"
API = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
BASE = f"https://github.com/{OWNER}/{REPO}"

# Preference order: the stable release-signed name first, then any build that
# is not a debug one.
PREFERRED_ASSETS = ("AutoWall.apk",)


class ReleaseError(RuntimeError):
    pass


def fetch_latest_release(timeout: float = 20.0) -> dict:
    request = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json"})
    request.add_header("User-Agent", "paid-apps-made-free-sync")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:  # pragma: no cover - network path
        raise ReleaseError(f"GitHub API returned {error.code} for {API}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:  # pragma: no cover
        raise ReleaseError(f"Could not read {API}: {error}") from error


def choose_apk(release: dict) -> dict:
    assets = [asset for asset in release.get("assets", []) if asset["name"].lower().endswith(".apk")]
    if not assets:
        raise ReleaseError(f"Release {release.get('tag_name')} has no .apk asset")

    by_name = {asset["name"]: asset for asset in assets}
    for candidate in PREFERRED_ASSETS:
        if candidate in by_name:
            return by_name[candidate]

    for asset in assets:
        if "debug" not in asset["name"].lower():
            return asset
    return assets[0]


def describe(release: dict) -> dict:
    asset = choose_apk(release)
    tag = (release.get("tag_name") or "").strip()
    if not tag:
        raise ReleaseError("Latest release has no tag name")
    return {
        "tag": tag,
        "asset": asset["name"],
        "size": asset.get("size"),
        "download": f"{BASE}/releases/latest/download/{asset['name']}",
        "install": f"{BASE}/releases/latest",
    }


def current_pins(html: str) -> dict:
    download = re.search(r'class="btn btn-primary" href="([^"]+)"', html)
    caption = re.search(r'<p class="caption">.*?</span>\s*(v[^<\s]+)\s*<', html, flags=re.DOTALL)
    return {
        "download": download.group(1) if download else None,
        "tag": caption.group(1) if caption else None,
    }


def rewrite(html: str, latest: dict) -> str:
    download = latest["download"]
    install = latest["install"]
    tag = latest["tag"]

    url_base = re.escape(BASE)

    # JSON-LD first: it holds the same two URLs in a different shape.
    html = re.sub(
        r'("downloadUrl":\s*")' + url_base + r'/releases/[^"]*(")',
        lambda match: f"{match.group(1)}{download}{match.group(2)}",
        html,
    )
    html = re.sub(
        r'("installUrl":\s*")' + url_base + r'/releases/[^"]*(")',
        lambda match: f"{match.group(1)}{install}{match.group(2)}",
        html,
    )

    # The download button: always the `latest` alias so it can never serve an
    # older build, with the asset name taken from the newest release.
    html, download_hits = re.subn(
        r'(class="btn btn-primary" href=")' + url_base + r'/releases/[^"]*(")',
        lambda match: f"{match.group(1)}{download}{match.group(2)}",
        html,
    )
    html, install_hits = re.subn(
        r'(class="btn btn-square" href=")' + url_base + r'/releases/[^"]*(")',
        lambda match: f"{match.group(1)}{install}{match.group(2)}",
        html,
    )
    html, caption_hits = re.subn(
        r'(<p class="caption">.*?</span>\s*)v[^<\s]+(\s*<)',
        lambda match: f"{match.group(1)}{tag}{match.group(2)}",
        html,
        flags=re.DOTALL,
    )

    if not (download_hits and install_hits and caption_hits):
        raise ReleaseError(
            "index.html no longer matches the expected download button / caption markup "
            f"(button={download_hits}, notes={install_hits}, caption={caption_hits})"
        )
    return html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 when index.html is out of date")
    parser.add_argument("--offline", action="store_true", help="print the pinned values and stop")
    args = parser.parse_args(argv)

    html = PAGE.read_text(encoding="utf-8")
    pinned = current_pins(html)

    if args.offline:
        print(json.dumps(pinned, indent=2))
        return 0

    try:
        latest = describe(fetch_latest_release())
    except ReleaseError as error:
        print(f"sync-release: {error}", file=sys.stderr)
        return 2

    megabytes = (latest["size"] or 0) / (1024 * 1024)
    print(f"latest: {latest['tag']} · {latest['asset']} ({megabytes:.1f} MB)")
    print(f"  download → {latest['download']}")

    updated = rewrite(html, latest)

    if args.check:
        if updated != html:
            print("index.html is out of date; run python3 tools/sync_release.py", file=sys.stderr)
            return 1
        print("index.html already points at the latest release")
        return 0

    if updated == html:
        print("index.html already up to date")
        return 0

    PAGE.write_text(updated, encoding="utf-8")
    print(f"index.html updated: {pinned['tag']} → {latest['tag']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

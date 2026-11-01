#!/usr/bin/env python3
"""Keep a permanent, version-independent download count for every app.

The catalogue is a static site. There is no server to count a click, and the
buttons jump straight to GitHub, so the only honest record of "someone
downloaded this app" is GitHub's own per-asset ``download_count``. The catch is
that GitHub counts *an asset*, not an app: publish v0.5.0 and the APK starts a
fresh counter at zero while v0.4.1 keeps its number.

So this script sums the ``download_count`` of every APK across *every* release
of the repository, drafts excluded, and stores one running total per app in
``data/downloads.json``. That file is committed, which makes the number:

* cumulative across versions (all releases are added together),
* immune to site edits (editing a slide never touches the data file), and
* monotonic (the stored total is only ever raised, so a deleted release or a
  GitHub hiccup can never make the counter jump backwards).

The page reads the file at runtime with ``counts.js`` and fills the small
counter beside each Download button.

Usage, from the repository root:

    python3 tools/sync_downloads.py            # refresh data/downloads.json
    python3 tools/sync_downloads.py --check    # validate the file, no network
    python3 tools/sync_downloads.py --offline  # print the stored totals as JSON

Set ``GITHUB_TOKEN`` in CI to stay well inside the API rate limit. Standard
library only; no dependencies.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_release import APPS  # noqa: E402 - one catalogue, shared with the pin sync

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "downloads.json"
PAGE = ROOT / "index.html"

NOTE = (
    "Cumulative APK downloads per app, summed across every GitHub release and "
    "never allowed to fall. Written by tools/sync_downloads.py; do not hand-edit."
)


class CountError(RuntimeError):
    pass


def releases_api(app: dict, page: int) -> str:
    return (
        f"https://api.github.com/repos/{app['owner']}/{app['repo']}"
        f"/releases?per_page=100&page={page}"
    )


def fetch_releases(app: dict, timeout: float = 20.0) -> list[dict]:
    """Return every published release, following the API's paging."""
    collected: list[dict] = []
    page = 1
    while True:
        request = urllib.request.Request(
            releases_api(app, page), headers={"Accept": "application/vnd.github+json"}
        )
        request.add_header("User-Agent", "paid-apps-made-free-downloads")
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                batch = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:  # pragma: no cover - network path
            raise CountError(f"GitHub API returned {error.code} for {releases_api(app, page)}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:  # pragma: no cover
            raise CountError(f"Could not read {releases_api(app, page)}: {error}") from error
        if not isinstance(batch, list):
            raise CountError(f"Unexpected payload for {releases_api(app, page)}")
        collected.extend(batch)
        if len(batch) < 100:
            return collected
        page += 1


def is_apk(asset: dict) -> bool:
    return str(asset.get("name", "")).lower().endswith(".apk")


def release_downloads(releases: Iterable[dict]) -> int:
    """Total APK downloads across every release, whatever the version.

    Drafts are invisible to everyone, so they are skipped. Pre-releases are
    included: a download of a beta is still a download of the app. Anything
    that is not an APK (checksums, symbols, notes) is not an install.
    """
    total = 0
    for release in releases:
        if release.get("draft"):
            continue
        for asset in release.get("assets", []) or []:
            if is_apk(asset):
                total += int(asset.get("download_count") or 0)
    return total


def load_data() -> dict:
    if not DATA.exists():
        return {"note": NOTE, "apps": {}}
    try:
        payload = json.loads(DATA.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CountError(f"{DATA} is not valid JSON: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("apps"), dict):
        raise CountError(f"{DATA} has no 'apps' object")
    return payload


def merge(previous: dict, fresh: dict) -> tuple[dict, list[str]]:
    """Keep the larger total per app, so a count can never go backwards."""
    merged: dict[str, dict] = {}
    raised: list[str] = []
    for app in APPS:
        app_id = app["id"]
        before = int((previous.get("apps", {}).get(app_id) or {}).get("total") or 0)
        after = int(fresh.get(app_id) or 0)
        total = max(before, after)
        if total > before:
            raised.append(f"{app['num']} {app['name']}: {before} -> {total}")
        merged[app_id] = {"name": app["name"], "total": total}
    return merged, raised


def write_data(totals: dict) -> bool:
    """Write the file only when a number actually moved; report whether it did."""
    current = load_data()
    if current.get("apps") == totals:
        return False
    payload = {
        "note": NOTE,
        "updated": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "apps": totals,
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


def check() -> int:
    """Structural check only: no network, safe to run in CI."""
    data = load_data()
    problems: list[str] = []
    known = {app["id"] for app in APPS}
    stored = set(data.get("apps", {}))
    missing = sorted(known - stored)
    extra = sorted(stored - known)
    if missing:
        problems.append(f"missing apps: {', '.join(missing)}")
    if extra:
        problems.append(f"unknown apps: {', '.join(extra)}")
    for app_id, entry in sorted(data.get("apps", {}).items()):
        total = entry.get("total") if isinstance(entry, dict) else None
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            problems.append(f"{app_id}: total must be a non-negative integer, got {total!r}")
    page = PAGE.read_text(encoding="utf-8")
    for app in APPS:
        if f'data-downloads="{app["id"]}"' not in page:
            problems.append(f"index.html has no counter slot for {app['id']}")
    if problems:
        print("download counts are not usable:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("download counts look good")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate data/downloads.json without network")
    parser.add_argument("--offline", action="store_true", help="print the stored totals as JSON")
    args = parser.parse_args(argv)

    if args.check:
        return check()
    if args.offline:
        print(json.dumps(load_data(), indent=2, sort_keys=True))
        return 0

    stored = load_data()
    fresh: dict[str, int] = {}
    for app in APPS:
        releases = fetch_releases(app)
        fresh[app["id"]] = release_downloads(releases)
        print(
            f"{app['num']} {app['name']}: {fresh[app['id']]} downloads "
            f"across {len([r for r in releases if not r.get('draft')])} releases"
        )

    totals, raised = merge(stored, fresh)
    changed = write_data(totals)
    for line in raised:
        print(f"  counted {line}")
    print("download counts updated" if changed else "download counts already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

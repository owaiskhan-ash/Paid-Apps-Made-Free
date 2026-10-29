#!/usr/bin/env python3
"""Keep every app's download button pointed at its newest release.

Each app in the catalogue is a slide on ``index.html``. GitHub's
``/releases/latest/download/<asset>`` alias already redirects to the newest
published release, so a button never downloads an old build. Two things can
still drift, though, and this script fixes both for every app:

1. the *asset file name*: if a release renames the APK, the alias 404s;
2. the visible version caption: it says whatever was current when the page was
   last edited.

It reads each app's GitHub release API, picks the installable APK, then
rewrites the slide (download button, release-notes button, caption) and the
JSON-LD entry so everything names the same, currently-latest release.

``--verify`` also asks GitHub where each button's ``latest`` alias actually
lands and fails unless it reaches the release the API just reported, so a
button that resolves to an older tag or a renamed asset cannot ship quietly.

Usage, from the repository root:

    python3 tools/sync_release.py           # update index.html
    python3 tools/sync_release.py --check    # exit 1 if any slide is out of date
    python3 tools/sync_release.py --verify   # also prove the latest aliases resolve
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
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "index.html"

# The catalogue, in slide order. Add a third app here and the sync picks it up.
APPS = (
    {
        "num": "01",
        "name": "AutoWall",
        "id": "app-01",
        "owner": "owaiskhan-ash",
        "repo": "Automatic-wallpaper-changer",
        # Stable release-signed name first, then anything that is not a debug build.
        "preferred": ("AutoWall.apk",),
        "operating_system": "Android 8.0+",
        "application_category": "UtilitiesApplication",
    },
    {
        "num": "02",
        "name": "Progress Tracker",
        "id": "app-02",
        "owner": "owaiskhan-ash",
        "repo": "Progress-Tracker",
        "preferred": ("Project-Tracker.apk",),
        "operating_system": "Android",
        "application_category": "ProductivityApplication",
    },
)


class ReleaseError(RuntimeError):
    pass


def app_base(app: dict) -> str:
    return f"https://github.com/{app['owner']}/{app['repo']}"


def app_api(app: dict) -> str:
    return f"https://api.github.com/repos/{app['owner']}/{app['repo']}/releases/latest"


def fetch_latest_release(app: dict, timeout: float = 20.0) -> dict:
    request = urllib.request.Request(app_api(app), headers={"Accept": "application/vnd.github+json"})
    request.add_header("User-Agent", "paid-apps-made-free-sync")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:  # pragma: no cover - network path
        raise ReleaseError(f"GitHub API returned {error.code} for {app_api(app)}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:  # pragma: no cover
        raise ReleaseError(f"Could not read {app_api(app)}: {error}") from error


def choose_apk(release: dict, preferred: tuple[str, ...]) -> dict:
    assets = [asset for asset in release.get("assets", []) if asset["name"].lower().endswith(".apk")]
    if not assets:
        raise ReleaseError(f"Release {release.get('tag_name')} has no .apk asset")

    by_name = {asset["name"]: asset for asset in assets}
    for candidate in preferred:
        if candidate in by_name:
            return by_name[candidate]

    for asset in assets:
        if "debug" not in asset["name"].lower():
            return asset
    return assets[0]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Leave 3xx responses unfollowed so the alias target stays inspectable."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - stdlib shape
        return None


def first_hop(url: str, timeout: float = 20.0) -> tuple[int, str | None]:
    """Return the status and redirect target of ``url`` without following it."""
    request = urllib.request.Request(url, method="HEAD")
    request.add_header("User-Agent", "paid-apps-made-free-sync")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.headers.get("Location")
    except urllib.error.HTTPError as error:
        if 300 <= error.code < 400:
            return error.code, error.headers.get("Location")
        raise ReleaseError(f"{url} returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:  # pragma: no cover - network path
        raise ReleaseError(f"Could not reach {url}: {error}") from error


def verify_latest_alias(app: dict, latest: dict, timeout: float = 20.0) -> None:
    """Prove GitHub's ``latest`` aliases really reach the release we pinned.

    The API says which release is newest, but only the live alias proves the
    buttons in the page follow it there. A release that renames the APK, or a
    button that still resolves to an older tag, fails here instead of shipping.
    """
    owner, repo = app["owner"], app["repo"]
    expected_download = f"/{owner}/{repo}/releases/download/{latest['tag']}/{latest['asset']}"
    expected_install = f"/{owner}/{repo}/releases/tag/{latest['tag']}"

    for label, url, expected in (
        ("download", latest["download"], expected_download),
        ("release page", latest["install"], expected_install),
    ):
        status, location = first_hop(url, timeout)
        if location is None:
            if 200 <= status < 300:
                # GitHub answered in place, so the alias itself is authoritative.
                continue
            raise ReleaseError(f"{app['num']} {app['name']}: {label} alias {url} returned HTTP {status}")
        landed = unquote(urlsplit(urljoin(url, location)).path)
        if landed != expected:
            raise ReleaseError(
                f"{app['num']} {app['name']}: {label} button resolves to {landed}, "
                f"not {expected}"
            )


def describe(app: dict, release: dict) -> dict:
    asset = choose_apk(release, app["preferred"])
    tag = (release.get("tag_name") or "").strip()
    if not tag:
        raise ReleaseError("Latest release has no tag name")
    base = app_base(app)
    return {
        "app": app,
        "tag": tag,
        "asset": asset["name"],
        "size": asset.get("size"),
        "download": f"{base}/releases/latest/download/{asset['name']}",
        "install": f"{base}/releases/latest",
    }


def slide_match(html: str, app_id: str):
    return re.search(
        r'(<section[^>]*id="%s"[^>]*>)(.*?)(</section>)' % re.escape(app_id),
        html,
        flags=re.DOTALL,
    )


def current_pins(html: str) -> dict:
    apps = []
    for app in APPS:
        match = slide_match(html, app["id"])
        download = tag = None
        if match:
            block = match.group(0)
            found = re.search(r'class="btn btn-primary" href="([^"]+)"', block)
            caption = re.search(r'<p class="caption">.*?</span>\s*(v[^<\s]+)\s*<', block, flags=re.DOTALL)
            download = found.group(1) if found else None
            tag = caption.group(1) if caption else None
        apps.append({"num": app["num"], "name": app["name"], "tag": tag, "download": download})
    return {"apps": apps}


def rewrite(html: str, app: dict, latest: dict) -> str:
    match = slide_match(html, app["id"])
    if not match:
        raise ReleaseError(f"index.html has no slide for {app['num']} {app['name']}")

    head, body, tail = match.group(1), match.group(2), match.group(3)
    esc = re.escape(app_base(app))

    # The download button: always the `latest` alias so it can never serve an
    # older build, with the asset name taken from the newest release.
    body, download_hits = re.subn(
        r'(class="btn btn-primary" href=")' + esc + r'/releases/[^"]*(")',
        lambda m: f'{m.group(1)}{latest["download"]}{m.group(2)}',
        body,
    )
    body, install_hits = re.subn(
        r'(class="btn btn-square" href=")' + esc + r'/releases/[^"]*(")',
        lambda m: f'{m.group(1)}{latest["install"]}{m.group(2)}',
        body,
    )
    body, caption_hits = re.subn(
        r'(<p class="caption">.*?</span>\s*)v[^<\s]+(\s*<)',
        lambda m: f'{m.group(1)}{latest["tag"]}{m.group(2)}',
        body,
        flags=re.DOTALL,
    )
    if not (download_hits and install_hits and caption_hits):
        raise ReleaseError(
            f"slide for {app['num']} {app['name']} no longer matches the expected "
            f"download button / caption markup "
            f"(button={download_hits}, notes={install_hits}, caption={caption_hits})"
        )

    html = html[: match.start()] + head + body + tail + html[match.end():]

    # Structured data carries the same two URLs in a different shape.
    html = re.sub(
        r'("downloadUrl":\s*")' + esc + r'/releases/[^"]*(")',
        lambda m: f'{m.group(1)}{latest["download"]}{m.group(2)}',
        html,
    )
    html = re.sub(
        r'("installUrl":\s*")' + esc + r'/releases/[^"]*(")',
        lambda m: f'{m.group(1)}{latest["install"]}{m.group(2)}',
        html,
    )
    return html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 when any slide is out of date")
    parser.add_argument("--verify", action="store_true", help="prove the live latest aliases reach the pinned releases")
    parser.add_argument("--offline", action="store_true", help="print the pinned values and stop")
    args = parser.parse_args(argv)

    html = PAGE.read_text(encoding="utf-8")
    pinned = current_pins(html)
    pinned_by_num = {entry["num"]: entry for entry in pinned["apps"]}

    if args.offline:
        print(json.dumps(pinned, indent=2))
        return 0

    latests: dict[str, dict] = {}
    for app in APPS:
        try:
            latests[app["num"]] = describe(app, fetch_latest_release(app))
        except ReleaseError as error:
            print(f"sync-release: {error}", file=sys.stderr)
            return 2
        latest = latests[app["num"]]
        megabytes = (latest["size"] or 0) / (1024 * 1024)
        print(f"{app['num']} {app['name']}: {latest['tag']} · {latest['asset']} ({megabytes:.1f} MB)")
        print(f"  download → {latest['download']}")

    if args.verify:
        for app in APPS:
            latest = latests[app["num"]]
            try:
                verify_latest_alias(app, latest)
            except ReleaseError as error:
                print(f"sync-release: {error}", file=sys.stderr)
                return 2
            print(f"{app['num']} {app['name']}: latest alias resolves to {latest['tag']}")

    updated = html
    for app in APPS:
        updated = rewrite(updated, app, latests[app["num"]])

    if args.check:
        if updated != html:
            print("index.html is out of date; run python3 tools/sync_release.py", file=sys.stderr)
            return 1
        print("index.html already points at the latest releases")
        return 0

    if updated == html:
        print("index.html already up to date")
        return 0

    PAGE.write_text(updated, encoding="utf-8")
    changed = ", ".join(
        f"{app['num']} {app['name']} {pinned_by_num[app['num']]['tag']} → {latests[app['num']]['tag']}"
        for app in APPS
        if pinned_by_num[app["num"]]["tag"] != latests[app["num"]]["tag"]
    )
    print(f"index.html updated: {changed or 'version labels unchanged'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

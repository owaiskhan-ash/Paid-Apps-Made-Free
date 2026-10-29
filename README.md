# Paid Apps Made Free

A one-screen, minimal landing page for **01 AutoWall** ([AutoWall on GitHub](https://github.com/owaiskhan-ash/Automatic-wallpaper-changer)), a free automatic wallpaper changer for Android.

Fluorescent background, hairline rules, thin type, and two outline buttons: a **Download** button that always resolves to the newest APK on GitHub Releases, and a small square shortcut to the release page.

## Preview locally

There is no build step and no JavaScript. From the repository root, run:

```sh
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Page anatomy

- `01 AutoWall` is the only headline on the page, with no body copy and no navigation.
- `FREE` sits in the top-right bar with no icon box on the landing page itself.
- `Download` points to `https://github.com/owaiskhan-ash/Automatic-wallpaper-changer/releases/latest/download/AutoWall.apk`.
  Because the path uses the `latest` release alias, it keeps working when a newer release is published; it never needs editing.
- The square `↗` button opens the release notes page.
- A tiny caption under the buttons records the release the button currently resolves to. It is kept in sync automatically (see below).
- The viewport opens with a short, reduced-motion-aware fade/rise; the hairline frame and rules stay static.

## Keeping the download on the latest release

Two independent safeguards:

1. **The link is versionless by construction.** It points at GitHub's
   `/releases/latest/download/<asset>` alias, which redirects to whatever release is
   newest at click time. There is no tag or version number in the URL, so a new
   release is picked up instantly with no deploy needed.
2. **A scheduled sync keeps the visible bits honest.** `tools/sync_release.py` reads
   the GitHub release API, picks the installable APK (stable name first, never a
   debug build unless it is the only option), and rewrites the download href, the
   release-notes href, the JSON-LD `downloadUrl`/`installUrl`, and the caption
   version. It exits non-zero instead of writing anything if the lookup fails or a
   release ships no APK, so a stale pin is never published silently.

`.github/workflows/sync-release.yml` runs that script daily, on manual dispatch, and
on a `repository_dispatch` of type `app-release`, then commits the refreshed label.
To make new releases land on the page within seconds instead of within a day, add
this step to the app repository's release workflow:

```yaml
- name: Nudge the catalogue
  uses: peter-evans/repository-dispatch@v3
  with:
    repository: owaiskhan-ash/Paid-Apps-Made-Free
    event-type: app-release
    token: ${{ secrets.CATALOGUE_DISPATCH_TOKEN }}
```

Manual runs:

```sh
python3 tools/sync_release.py            # rewrite the page to the newest release
python3 tools/sync_release.py --check    # CI: exit 1 if the page is stale
python3 tools/sync_release.py --offline  # just print what the page currently pins
```

Set `GITHUB_TOKEN` for unattended runs to avoid the anonymous API rate limit.

## Quality checks

Standard-library SEO, structured-data, CSP, asset, release-link, and
release-sync checks (no network needed):

```sh
python3 -m unittest discover -s tests -v
```

## Brand icons and social share card

- `assets/free-app-icon.png` (1280×1280) is the high-resolution fluorescent debossed `FREE` icon saved in the repository and used as the site favicon (`assets/favicon-32x32.png`, `favicon.ico`, and `assets/apple-touch-icon.png`).
- `assets/og-image.png` (1200×630) is the Open Graph / X social share card for `01 AutoWall`.

To refresh derived favicon sizes from `assets/free-app-icon.png` (requires ImageMagick `convert`):

```sh
python3 tools/make_assets.py
```

## SEO and answer-engine notes

- `index.html` keeps the canonical URL, share metadata, and Schema.org `Organization`, `WebSite`, `WebPage`, and `SoftwareApplication` data. The app entry declares the same `downloadUrl` the button uses.
- `robots.txt` allows crawling and points to the single-URL `sitemap.xml`.
- `llms.txt` summarises the site for tools that choose to read it.
- The Content Security Policy in `vercel.json` blocks inline executable code. JSON-LD is a non-executable data block, so crawlers can read it without weakening `script-src`.
- `404.html` is intentionally noindex and matches the same minimal layout.

## Deployment

Zero-build static site served from the repository root by Vercel. `vercel.json` adds security headers and redirects the old `*.vercel.app` host to the canonical domain. No secrets, environment variables, or third-party runtime scripts are required.

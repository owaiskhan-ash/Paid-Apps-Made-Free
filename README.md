# Paid Apps Made Free

A minimal slideshow landing page that publishes free Android apps **one slide at a time**:

- **01 AutoWall** ([AutoWall on GitHub](https://github.com/owaiskhan-ash/Automatic-wallpaper-changer)), a free automatic wallpaper changer for Android.
- **02 Progress Tracker** ([Progress Tracker on GitHub](https://github.com/owaiskhan-ash/Progress-Tracker)), a free project progress tracker for Android with an on-device widget.

Fluorescent background, hairline rules, thin type, and two outline buttons per slide: a **Download** button that always resolves to the newest APK on GitHub Releases, and a small square shortcut to the release page. The top bar walks the catalogue like slides, one app on screen at a time, and no JavaScript is required.

## Preview locally

There is no build step and no JavaScript. From the repository root, run:

```sh
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Slideshow anatomy

- The page is a deck of `<section class="slide">` blocks. Exactly one is visible at a time: the slide named by the URL fragment, or `01 AutoWall` when the URL has no fragment.
- `01` and `02` tabs (plus the arrow keys in the top bar) switch slides by changing `#app-01` / `#app-02`, so each app has a shareable URL (`/#app-02`) and the page keeps working without JavaScript.
- `FREE` sits in the top-right bar with no icon box on the page itself.
- Each slide's `Download` button points at `https://github.com/<owner>/<repo>/releases/latest/download/<asset>`. Because the path uses the `latest` release alias, it keeps working when a newer release is published; it never needs editing.
- The square `↗` button on each slide opens that app's release notes page.
- A tiny caption under the buttons records the release each button currently resolves to. It is kept in sync automatically (see below).
- The viewport opens with a short, reduced-motion-aware fade/rise; the hairline frame and rules stay static.

## Keeping the downloads on the latest release

Two independent safeguards:

1. **The links are versionless by construction.** Each points at GitHub's
   `/releases/latest/download/<asset>` alias, which redirects to whatever release is
   newest at click time. There is no tag or version number in the URL, so a new
   release is picked up instantly with no deploy needed.
2. **A scheduled sync keeps the visible bits honest.** `tools/sync_release.py` reads
   each app's GitHub release API, picks the installable APK (stable name first, never a
   debug build unless it is the only option), and rewrites the slide's download href,
   release-notes href, JSON-LD `downloadUrl`/`installUrl`, and caption version. It exits
   non-zero instead of writing anything if a lookup fails or a release ships no APK, so a
   stale pin is never published silently.

`.github/workflows/sync-release.yml` runs that script daily, on manual dispatch, and
on a `repository_dispatch` of type `app-release`, then commits the refreshed labels.
To make new releases land on the page within seconds instead of within a day, add
this step to each app repository's release workflow:

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
python3 tools/sync_release.py            # rewrite every slide to the newest release
python3 tools/sync_release.py --check    # CI: exit 1 if any slide is stale
python3 tools/sync_release.py --offline  # just print what each slide currently pins
```

Set `GITHUB_TOKEN` for unattended runs to avoid the anonymous API rate limit.

To add a third app, append an entry to the `APPS` tuple in `tools/sync_release.py`
and add a matching slide to `index.html`.

## Quality checks

Standard-library SEO, structured-data, CSP, asset, release-link, and
release-sync checks (no network needed):

```sh
python3 -m unittest discover -s tests -v
```

## Brand icons and social share card

- `assets/free-app-icon.png` (1280×1280) is the high-resolution fluorescent debossed `FREE` icon saved in the repository and used as the site favicon (`assets/favicon-32x32.png`, `favicon.ico`, and `assets/apple-touch-icon.png`).
- `assets/og-image.png` (1200×630) is the Open Graph / X social share card.

To refresh derived favicon sizes from `assets/free-app-icon.png` (requires ImageMagick `convert`):

```sh
python3 tools/make_assets.py
```

## SEO and answer-engine notes

- `index.html` keeps the canonical URL, share metadata, and Schema.org `Organization`, `WebSite`, two `WebPage` entries (one per app), and two `SoftwareApplication` entries. Each app entry declares the same `downloadUrl` its button uses.
- `robots.txt` allows crawling and points to the single-URL `sitemap.xml`.
- `llms.txt` summarises the site for tools that choose to read it.
- The Content Security Policy in `vercel.json` blocks inline executable code. JSON-LD is a non-executable data block, so crawlers can read it without weakening `script-src`.
- `404.html` is intentionally noindex and matches the same minimal layout.

## Deployment

Zero-build static site served from the repository root by Vercel. `vercel.json` adds security headers and redirects the old `*.vercel.app` host to the canonical domain. No secrets, environment variables, or third-party runtime scripts are required.

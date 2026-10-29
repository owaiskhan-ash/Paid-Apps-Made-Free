# Paid Apps Made Free

A one-screen, minimal landing page for **App 01** — [AutoWall](https://github.com/owaiskhan-ash/Automatic-wallpaper-changer), a free automatic wallpaper changer for Android.

Fluorescent background, hairline rules, thin type, and two outline buttons: a **Download** button that always resolves to the newest APK on GitHub Releases, and a small square shortcut to the release page.

## Preview locally

There is no build step and no JavaScript. From the repository root, run:

```sh
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Page anatomy

- `App 01` is the only headline on the page — no body copy, no navigation.
- `Download` → `https://github.com/owaiskhan-ash/Automatic-wallpaper-changer/releases/latest/download/AutoWall.apk`
  Because the path uses the `latest` release alias, it keeps working when a newer release is published; it never needs editing.
- The square `↗` button opens the release notes page.
- A tiny caption under the buttons records the release the page was checked against (`v1.2.0`). Update that one string on a new release — the download link itself does not change.
- The viewport opens with a short, reduced-motion-aware fade/rise; the hairline frame and rules stay static.

## Quality checks

Standard-library SEO, structured-data, CSP, asset, and release-link checks:

```sh
python3 -m unittest discover -s tests -v
```

## Regenerating images

`assets/og-image.png` (1200×630) and `assets/apple-touch-icon.png` (180×180) are drawn by a dependency-free rasteriser, so they can be regenerated without ImageMagick, a browser, or fonts:

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

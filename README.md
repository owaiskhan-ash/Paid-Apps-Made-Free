# Paid Apps Made Free

A minimal, fluorescent deck of one-screen-per-app cards. Two screens, two thin outline buttons each, no body copy.

- **App 01** — [AutoWall](https://github.com/owaiskhan-ash/Automatic-wallpaper-changer), automatic wallpaper changer.
- **App 02** — [Project Progress](https://github.com/owaiskhan-ash/Project-Progress-Widget), project tracker widget.

## Preview locally

No build step. From the repository root:

```sh
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Page anatomy

Each screen is the same thin layout: hairline rules, `APP 0x` headline, an outlined **Download** button, a square `↗` release-notes button, a small release caption, and a `Next >` control in the bottom bar.

- **Download** points at the newest APK through GitHub's `latest` alias, so it never needs editing when a release ships:
  - App 01 → `.../Automatic-wallpaper-changer/releases/latest/download/AutoWall.apk`
  - App 02 → `.../Project-Progress-Widget/releases/latest/download/app-debug.apk`
- The caption records the version the page was checked against (`v1.2.0` for both). Update that one string per release; the download link itself is stable.
- `Next >` advances, the second screen's control becomes `< Back`, and both return to the matching slide direction.

## Slide choreography

Clicking `Next` never snaps. The two layers move in sequence:

1. **Outgoing, text first** — headline, then buttons, then caption step out (26 px, 0 / 55 / 110 ms), the bars follow, and only then do the hairlines slide off (delay 320 ms).
2. **Arriving, lines first** — the hairlines slide in from the direction of travel (starts at 250 ms), and the text lands after them at 620–790 ms.

The deck locks for ~1.2 s per transition so the sequence cannot be interrupted halfway, and taps are ignored while it plays. Direction is flipped via `data-dir="forward|back"` on the deck, so `Back` mirrors the motion.

Extras:

- `ArrowRight` / `ArrowLeft` move between screens.
- The URL hash tracks the live screen (`#app-01`, `#app-02`) through `replaceState`, so a screen can be linked directly.
- `prefers-reduced-motion` shortens every step to 1 ms.
- Without JavaScript the deck falls back to two stacked screens that scroll normally, and the `Next` controls are hidden (`@media (scripting: none)`).
- Focus follows the reader: it is moved to the new screen's control only if it was already inside the outgoing screen, and parked screens are `inert`.

## Quality checks

Standard-library SEO, structured-data, CSP, asset, release-link, and choreography-order checks:

```sh
python3 -m unittest discover -s tests -v
```

## Regenerating images

`assets/og-image.png` (1200×630) and `assets/apple-touch-icon.png` (180×180) are drawn by a dependency-free rasteriser — no browser, ImageMagick, or fonts required:

```sh
python3 tools/make_assets.py
```

## SEO notes

- Canonical URL, share metadata, and Schema.org `Organization`, `WebSite`, `WebPage`, and an `ItemList` of the two `SoftwareApplication` entries. Each entry's `downloadUrl` matches its button.
- `robots.txt` allows crawling and points to the single-URL `sitemap.xml`; `llms.txt` summarises the site for tools that read it.
- The Content Security Policy in `vercel.json` blocks inline executable code, so the deck lives in `app.js` (`script-src 'self'`). JSON-LD is a non-executable data block and stays inline.
- `404.html` is intentionally noindex and uses the same minimal layout.

## Deployment

Zero-build static site served from the repository root by Vercel. `vercel.json` adds security headers and redirects the old `*.vercel.app` host to the canonical domain. No secrets, environment variables, or third-party runtime scripts are required.

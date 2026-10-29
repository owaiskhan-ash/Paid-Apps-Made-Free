# Paid Apps Made Free

A lightweight, accessible, static landing page and practical guide to limited-time app promotions for `https://free.justsimpleapps.online/`.

## Preview locally

There is no build step or JavaScript dependency. From the repository root, run:

```sh
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Quality checks

Run the standard-library SEO, structured-data, CSP, and asset checks with:

```sh
python3 -m unittest discover -s tests -v
```

## SEO and answer-engine notes

- `index.html` contains the canonical URL, share metadata, answer-first copy, visible FAQs, and matching Schema.org `WebSite`, `WebPage`, `Organization`, and `FAQPage` data.
- `robots.txt` allows crawling and points to the single-URL `sitemap.xml`.
- `llms.txt` summarizes the site for tools that choose to read it. It is supplemental and is not a search-ranking guarantee.
- The Content Security Policy in `vercel.json` blocks inline executable JavaScript. JSON-LD is a non-executable data block, so crawlers can read it without weakening `script-src`.
- `404.html` is intentionally noindex and gives users a useful way back to the homepage.

## Deal-board integrity

The live offer feed is not connected. The page says so rather than publishing invented app names, prices, or expiry dates. Keep that disclosure until a verified data source is integrated. Any future offer should link to its official store page and be checked for region, current price, and in-app purchase terms.

## Deployment

The project is a zero-build static site that can be served from the repository root by Vercel. `vercel.json` adds security headers; no secrets, environment variables, or third-party runtime scripts are required.

import json
import re
import struct
import unittest
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "https://free.justsimpleapps.online/"
RELEASES = "https://github.com/owaiskhan-ash/Automatic-wallpaper-changer/releases/latest"
DOWNLOAD = f"{RELEASES}/download/AutoWall.apk"
APP_02 = "https://github.com/owaiskhan-ash/Project-Progress-Widget/releases/latest"
DOWNLOAD_02 = f"{APP_02}/download/app-debug.apk"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading_one_count = 0
        self.images = []
        self.links = []
        self.local_assets = []
        self.external_scripts = []
        self.inline_styles = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self.heading_one_count += 1
        if tag == "img":
            self.images.append(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "script" and attrs.get("src"):
            self.external_scripts.append(attrs["src"])
        if tag == "style" or ("style" in attrs):
            self.inline_styles += 1
        if tag in {"link", "img", "script"}:
            url = attrs.get("href") or attrs.get("src")
            if url and url.startswith("/") and not url.startswith("//"):
                self.local_assets.append(url)


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


class LandingPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.parser = PageParser()
        cls.parser.feed(cls.html)
        cls.visible_parser = VisibleTextParser()
        cls.visible_parser.feed(cls.html)
        cls.visible_text = " ".join(cls.visible_parser.parts)
        cls.schema_match = re.search(
            r'<script\s+type="application/ld\+json">(.*?)</script>',
            cls.html,
            flags=re.DOTALL,
        )
        if not cls.schema_match:
            raise AssertionError("Missing JSON-LD structured data")
        cls.schema = json.loads(cls.schema_match.group(1))

    def test_canonical_and_indexable_metadata(self):
        self.assertIn(f'<link rel="canonical" href="{CANONICAL}">', self.html)
        self.assertRegex(self.html, r"<title>[^<]{15,70}</title>")
        self.assertRegex(self.html, r'<meta name="description" content="[^"]{60,180}">')
        self.assertIn(
            '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">',
            self.html,
        )
        self.assertEqual(self.parser.heading_one_count, 1, "Use exactly one H1")

    def test_headline_is_the_app_number_only(self):
        headline = re.search(r"<h1[^>]*>(.*?)</h1>", self.html, flags=re.DOTALL).group(1)
        headline_text = re.sub(r"<[^>]+>", "", headline).strip()
        self.assertEqual(re.sub(r"\s+", " ", headline_text), "App 01")
        second = re.search(r"<h2[^>]*>(.*?)</h2>", self.html, flags=re.DOTALL).group(1)
        self.assertEqual(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", second)).strip(), "App 02")
        self.assertEqual(self.parser.images, [], "The minimal page uses no raster imagery")

    def test_two_screens_are_present_and_only_one_starts_live(self):
        screens = re.findall(r'<section class="screen ([^"]+)" id="(app-0\d)"', self.html)
        self.assertEqual(screens, [("is-active is-booting", "app-01"), ("is-parked", "app-02")])
        self.assertEqual(self.html.count('class="screen '), 2)
        self.assertIn("data-deck", self.html)
        self.assertEqual(self.html.count('class="lines" aria-hidden="true"'), 2)

    def test_next_control_is_a_small_chevron_button_not_the_android_tag(self):
        self.assertIn('data-goto="1"', self.html)
        self.assertIn('data-goto="0"', self.html)
        self.assertRegex(self.html, r'<button class="nav" type="button" data-goto="1"[^>]*>\s*<span>Next</span>')
        self.assertRegex(self.html, r'<svg class="nav-arrow[^"]*" viewBox="0 0 6 10"')
        self.assertNotIn(">Android<", self.visible_text)
        self.assertEqual(len(re.findall(r"\bAndroid\b", self.visible_text)), 1, "The Android tag was replaced by Next")

    def test_open_graph_and_twitter_share_assets_exist(self):
        self.assertIn(f'property="og:url" content="{CANONICAL}"', self.html)
        self.assertIn('name="twitter:card" content="summary_large_image"', self.html)
        image = (ROOT / "assets/og-image.png").read_bytes()
        self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", image[16:24]), (1200, 630))
        icon = (ROOT / "assets/apple-touch-icon.png").read_bytes()
        self.assertEqual(icon[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", icon[16:24]), (180, 180))

    def test_download_buttons_target_the_latest_release_apk_for_both_apps(self):
        self.assertIn(f'href="{DOWNLOAD}"', self.html)
        self.assertIn(f'href="{RELEASES}"', self.html)
        self.assertIn(f'href="{DOWNLOAD_02}"', self.html)
        self.assertIn(f'href="{APP_02}"', self.html)
        self.assertEqual(len(re.findall(r"\bDownload\b", self.visible_text)), 2)
        releases = [href for href in self.parser.links if "/releases/" in href]
        self.assertEqual(releases, [DOWNLOAD, RELEASES, DOWNLOAD_02, APP_02])
        self.assertEqual(self.html.count('rel="noopener"'), 4)
        self.assertEqual(self.html.count('target="_blank"'), 4)

    def test_structured_data_matches_the_published_app(self):
        graph = self.schema["@graph"]
        graph_types = {item["@type"] for item in graph}
        self.assertTrue({"Organization", "WebSite", "WebPage", "ItemList"}.issubset(graph_types))
        app_list = next(item for item in graph if item["@type"] == "ItemList")
        self.assertEqual(app_list["numberOfItems"], 2)
        first, second = [entry["item"] for entry in app_list["itemListElement"]]
        self.assertEqual((first["alternateName"], second["alternateName"]), ("App 01", "App 02"))
        self.assertEqual(first["downloadUrl"], DOWNLOAD)
        self.assertEqual(first["installUrl"], RELEASES)
        self.assertEqual(second["downloadUrl"], DOWNLOAD_02)
        self.assertEqual(second["installUrl"], APP_02)
        self.assertEqual({first["offers"]["price"], second["offers"]["price"]}, {"0"})

    def test_crawler_files_point_to_the_canonical_host(self):
        robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        self.assertIn("Allow: /", robots)
        self.assertIn(f"Sitemap: {CANONICAL}sitemap.xml", robots)
        xml_root = ElementTree.fromstring(sitemap)
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_urls = [node.text for node in xml_root.findall("s:url/s:loc", namespace)]
        self.assertEqual(sitemap_urls, [CANONICAL])
        self.assertIn(CANONICAL, llms)
        self.assertNotIn("https://paid-apps-made-free.vercel.app", self.html + sitemap + robots)

    def test_old_vercel_host_redirects_to_the_custom_canonical_domain(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        redirect = config["redirects"][0]
        self.assertEqual(redirect["has"], [{"type": "host", "value": "paid-apps-made-free.vercel.app"}])
        self.assertEqual(redirect["destination"], "https://free.justsimpleapps.online/:path*")
        self.assertTrue(redirect["permanent"])

    def test_csp_blocks_inline_code_and_security_headers_exist(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        headers = config["headers"][0]["headers"]
        policies = {header["key"].lower(): header["value"] for header in headers}
        csp = policies["content-security-policy"]
        script_policy = next(part.strip() for part in csp.split(";") if part.strip().startswith("script-src"))
        self.assertEqual(script_policy, "script-src 'self'")
        self.assertNotIn("unsafe-inline", csp)
        self.assertIn("application/ld+json", self.html)
        self.assertIn("object-src 'none'", csp)
        self.assertEqual(policies["x-content-type-options"], "nosniff")
        self.assertEqual(policies["x-frame-options"], "DENY")
        self.assertIn("strict-origin-when-cross-origin", policies["referrer-policy"])

    def test_static_assets_resolve_and_only_the_local_script_runs(self):
        self.assertEqual(self.parser.external_scripts, ["/app.js"], "Only the first-party deck script may run")
        self.assertEqual(self.parser.inline_styles, 0, "Styles must remain in the CSP-approved stylesheet")
        self.assertEqual(self.html.count("<script"), 2, "One JSON-LD data block and one local script")
        for asset in self.parser.local_assets:
            path = (ROOT / asset.lstrip("/")).resolve()
            self.assertTrue(path.is_relative_to(ROOT), f"Asset path escaped repo: {asset}")
            self.assertTrue(path.exists(), f"Missing local asset: {asset}")

    def test_deck_script_choreographs_text_then_lines(self):
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        for token in ("is-leaving", "is-entering", "is-parked", "data-goto", "prefers-reduced-motion", "ArrowRight"):
            self.assertIn(token, js)
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        # Text leaves first, then the hairlines; on arrival the hairlines land before the text.
        leaving_text = css.index(".screen.is-leaving .layer-text {")
        leaving_lines = css.index(".screen.is-leaving .lines {")
        entering_lines = css.index(".screen.is-entering .lines {")
        entering_text = css.index(".screen.is-entering .layer-text {")
        self.assertLess(leaving_text, leaving_lines)
        self.assertLess(entering_lines, entering_text)
        self.assertIn("var(--out-lines) 320ms", css)
        self.assertIn("var(--in-lines) 430ms", css)
        self.assertIn("@media (scripting: none)", css)

    def test_stylesheet_stays_thin_and_fluorescent(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("--fluoro: #ccff00", css)
        self.assertIn("font-weight: 300", css)
        self.assertIn("border: var(--hairline) solid var(--ink)", css)
        self.assertNotIn("box-shadow", css)
        self.assertNotIn("border-radius: 0.75rem", css)

    def test_404_is_noindex_and_returns_users_to_home(self):
        not_found = (ROOT / "404.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="robots" content="noindex, nofollow">', not_found)
        self.assertIn('href="/"', not_found)
        self.assertIn("Page not found", not_found)


if __name__ == "__main__":
    unittest.main()

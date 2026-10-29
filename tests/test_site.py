import contextlib
import importlib.util
import io
import json
import re
import struct
import unittest
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "https://free.justsimpleapps.online/"

# 01 AutoWall
RELEASES_01 = "https://github.com/owaiskhan-ash/Automatic-wallpaper-changer/releases/latest"
ASSET_01 = "AutoWall.apk"
DOWNLOAD_01 = f"{RELEASES_01}/download/{ASSET_01}"

# 02 Progress Tracker
RELEASES_02 = "https://github.com/owaiskhan-ash/Progress-Tracker/releases/latest"
ASSET_02 = "Project-Tracker.apk"
DOWNLOAD_02 = f"{RELEASES_02}/download/{ASSET_02}"


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
        self.assertEqual(self.parser.heading_one_count, 2, "One H1 per app slide")

    def test_slides_are_numbered_and_show_one_app_each(self):
        headlines = re.findall(r"<h1[^>]*>(.*?)</h1>", self.html, flags=re.DOTALL)
        texts = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip() for text in headlines]
        self.assertEqual(texts, ["01 AutoWall", "02 Progress Tracker"])

        slide_ids = re.findall(r'<section class="slide[^"]*" id="(app-\d+)"', self.html)
        self.assertEqual(slide_ids, ["app-01", "app-02"])
        self.assertEqual(self.parser.images, [], "The minimal slides use no raster imagery")

    def test_top_bar_shows_navigation_and_free_on_right_without_box(self):
        top_bar = re.search(r'<header class="bar bar-top">(.*?)</header>', self.html, flags=re.DOTALL).group(1)
        self.assertNotIn('class="mark"', top_bar)
        self.assertIn("nav", top_bar)
        self.assertIn("FREE", re.sub(r"<[^>]+>", " ", top_bar))
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        bar_top_block = re.search(r"\.bar-top\s*\{([^}]*)\}", css, flags=re.DOTALL).group(1)
        self.assertIn("justify-content: space-between", bar_top_block)

    def test_slideshow_keeps_one_slide_visible_at_a_time(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.slide\s*\{[^}]*display:\s*none", "Slides start hidden")
        self.assertIn(".slide:target", css)
        self.assertIn(":has(.slide:target)", css)
        self.assertIn(".deck:not(:has(.slide:target)) .slide:first-of-type", css)

    def test_no_em_dashes_in_site_copy_or_metadata(self):
        for rel in ("index.html", "404.html", "llms.txt", "README.md", "site.webmanifest"):
            content = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("—", content, f"Found em dash in {rel}")
            self.assertNotIn("&mdash;", content, f"Found &mdash; in {rel}")
            self.assertNotIn("&#8212;", content, f"Found &#8212; in {rel}")

    def test_open_graph_google_vercel_and_manifest_icons_exist(self):
        self.assertIn(f'property="og:url" content="{CANONICAL}"', self.html)
        self.assertIn('property="og:title" content="Paid Apps Made Free"', self.html)
        self.assertIn('name="twitter:card" content="summary_large_image"', self.html)
        self.assertIn('name="twitter:title" content="Paid Apps Made Free"', self.html)

        image = (ROOT / "assets/og-image.png").read_bytes()
        self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", image[16:24]), (1200, 630))

        expected_pngs = {
            "assets/favicon-16x16.png": (16, 16),
            "assets/favicon-32x32.png": (32, 32),
            "assets/favicon-48x48.png": (48, 48),
            "assets/favicon-96x96.png": (96, 96),
            "assets/apple-touch-icon.png": (180, 180),
            "apple-touch-icon.png": (180, 180),
            "assets/icon-192x192.png": (192, 192),
            "favicon.png": (192, 192),
            "assets/icon-512x512.png": (512, 512),
            "assets/free-app-icon.png": (1280, 1280),
        }
        for rel, dims in expected_pngs.items():
            raw = (ROOT / rel).read_bytes()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n", f"{rel} must be PNG")
            self.assertEqual(struct.unpack(">II", raw[16:24]), dims, f"{rel} wrong size")

        # Google Search requires multiples of 48px (48x48, 96x96, 192x192)
        self.assertIn('href="/assets/favicon-48x48.png" type="image/png" sizes="48x48"', self.html)
        self.assertIn('href="/assets/favicon-96x96.png" type="image/png" sizes="96x96"', self.html)
        self.assertIn('href="/assets/icon-192x192.png" type="image/png" sizes="192x192"', self.html)
        self.assertIn('href="/favicon.ico"', self.html)
        self.assertIn('href="/site.webmanifest"', self.html)

        ico = (ROOT / "favicon.ico").read_bytes()
        self.assertEqual(ico[:4], b"\x00\x00\x01\x00", "favicon.ico must have valid ICO header")

        manifest = json.loads((ROOT / "site.webmanifest").read_text(encoding="utf-8"))
        manifest_srcs = {entry["src"] for entry in manifest["icons"]}
        self.assertIn("/assets/icon-192x192.png", manifest_srcs)
        self.assertIn("/assets/icon-512x512.png", manifest_srcs)
        for src in manifest_srcs:
            self.assertTrue((ROOT / src.lstrip("/")).exists(), f"Missing manifest icon: {src}")

    def test_download_buttons_target_the_latest_release_apk_for_every_app(self):
        for download, releases in ((DOWNLOAD_01, RELEASES_01), (DOWNLOAD_02, RELEASES_02)):
            self.assertIn(f'href="{download}"', self.html)
            self.assertIn(f'href="{releases}"', self.html)
        self.assertIn("Download", self.visible_text)
        downloads = [href for href in self.parser.links if "/releases/" in href]
        self.assertEqual(downloads, [DOWNLOAD_01, RELEASES_01, DOWNLOAD_02, RELEASES_02])
        self.assertIn('rel="noopener"', self.html)
        self.assertIn('target="_blank"', self.html)

    def test_structured_data_covers_the_organization_and_both_apps(self):
        graph = self.schema["@graph"]
        graph_types = {item["@type"] for item in graph}
        self.assertTrue({"Organization", "WebSite", "WebPage", "SoftwareApplication"}.issubset(graph_types))

        org = next(item for item in graph if item["@type"] == "Organization")
        self.assertEqual(org["logo"]["url"], f"{CANONICAL}assets/icon-512x512.png")

        apps = [item for item in graph if item["@type"] == "SoftwareApplication"]
        self.assertEqual(len(apps), 2, "One SoftwareApplication entry per app")
        for app, download, releases in ((apps[0], DOWNLOAD_01, RELEASES_01), (apps[1], DOWNLOAD_02, RELEASES_02)):
            self.assertEqual(app["downloadUrl"], download)
            self.assertEqual(app["installUrl"], releases)
            self.assertEqual(app["offers"]["price"], "0")
            self.assertEqual(app["image"], f"{CANONICAL}assets/icon-512x512.png")

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
        self.assertIn("manifest-src 'self'", csp)
        self.assertEqual(policies["x-content-type-options"], "nosniff")
        self.assertEqual(policies["x-frame-options"], "DENY")
        self.assertIn("strict-origin-when-cross-origin", policies["referrer-policy"])

    def test_static_assets_resolve_and_no_inline_or_external_runtime_code(self):
        self.assertEqual(self.parser.external_scripts, [], "The page should not depend on runtime scripts")
        self.assertEqual(self.parser.inline_styles, 0, "Styles must remain in the CSP-approved stylesheet")
        for asset in self.parser.local_assets:
            path = (ROOT / asset.lstrip("/")).resolve()
            self.assertTrue(path.is_relative_to(ROOT), f"Asset path escaped repo: {asset}")
            self.assertTrue(path.exists(), f"Missing local asset: {asset}")

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
        self.assertNotIn('class="mark"', not_found)


class ReleaseSyncTests(unittest.TestCase):
    """Every download button must resolve to whichever release is newest."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("sync_release", ROOT / "tools/sync_release.py")
        cls.sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.sync)
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.autowall = cls.sync.APPS[0]
        cls.progress = cls.sync.APPS[1]

    @staticmethod
    def release(tag, *names):
        return {
            "tag_name": tag,
            "assets": [{"name": name, "size": 1024, "browser_download_url": "https://x/" + name} for name in names],
        }

    def test_every_button_is_pinned_to_the_mutable_latest_alias(self):
        pinned = {entry["num"]: entry for entry in self.sync.current_pins(self.html)["apps"]}
        for app, base in ((self.autowall, RELEASES_01), (self.progress, RELEASES_02)):
            self.assertTrue(
                pinned[app["num"]]["download"].startswith(base + "/download/"),
                "The download button must use /releases/latest/download/, never a versioned URL",
            )
            self.assertNotRegex(pinned[app["num"]]["download"], r"/download/v?\d")
            self.assertRegex(pinned[app["num"]]["tag"], r"^v\d+\.\d+")

    def test_prefers_the_stable_asset_name_over_tag_stamped_or_debug_builds(self):
        chosen = self.sync.choose_apk(
            self.release("v9.9.9", "AutoWall-debug.apk", "AutoWall-9.9.9.apk", "AutoWall.apk"),
            self.autowall["preferred"],
        )
        self.assertEqual(chosen["name"], "AutoWall.apk")
        chosen = self.sync.choose_apk(
            self.release("v9.9.9", "Project-Tracker-debug.apk", "Project-Tracker-9.9.9.apk", "Project-Tracker.apk"),
            self.progress["preferred"],
        )
        self.assertEqual(chosen["name"], "Project-Tracker.apk")

    def test_falls_back_when_the_asset_name_changes(self):
        self.assertEqual(
            self.sync.choose_apk(self.release("v2.0.0", "AutoWall-2.0.0.apk", "checksums.txt"), self.autowall["preferred"])["name"],
            "AutoWall-2.0.0.apk",
        )
        self.assertEqual(
            self.sync.choose_apk(self.release("v2.0.1", "AutoWall-debug.apk"), self.autowall["preferred"])["name"],
            "AutoWall-debug.apk",
        )
        with self.assertRaises(self.sync.ReleaseError):
            self.sync.choose_apk(self.release("v2.0.2", "notes.md"), self.autowall["preferred"])

    def test_rewrite_moves_every_reference_to_the_new_release(self):
        latest = self.sync.describe(self.autowall, self.release("v7.0.0", "AutoWall-7.0.0.apk", "AutoWall.apk"))
        self.assertEqual(latest["download"], DOWNLOAD_01)

        rewritten = self.sync.rewrite(self.html, self.autowall, latest)
        self.assertIn('href="' + DOWNLOAD_01 + '"', rewritten)
        self.assertIn('"downloadUrl": "' + DOWNLOAD_01 + '"', rewritten)
        self.assertIn('"installUrl": "' + RELEASES_01 + '"', rewritten)
        self.assertIn("v7.0.0", rewritten)
        self.assertNotIn("v1.3.0", rewritten)
        self.assertEqual(self.sync.rewrite(rewritten, self.autowall, latest), rewritten, "rewrite should be idempotent")

    def test_rewrite_updates_the_second_app_in_place(self):
        latest = self.sync.describe(self.progress, self.release("v2.2.2", "Project-Tracker.apk"))
        rewritten = self.sync.rewrite(self.html, self.progress, latest)
        self.assertIn('href="' + DOWNLOAD_02 + '"', rewritten)
        self.assertIn('"downloadUrl": "' + DOWNLOAD_02 + '"', rewritten)
        self.assertIn('"installUrl": "' + RELEASES_02 + '"', rewritten)
        self.assertIn("v2.2.2", rewritten)
        self.assertNotIn("v1.1.5", rewritten)
        # The first app's slide is untouched.
        self.assertIn("v1.3.0", rewritten)

    def test_asset_rename_is_carried_into_the_page(self):
        latest = self.sync.describe(self.autowall, self.release("v8.0.0", "AutoWall-v8.apk"))
        rewritten = self.sync.rewrite(self.html, self.autowall, latest)
        self.assertIn(RELEASES_01 + "/download/AutoWall-v8.apk", rewritten)

    def test_a_release_without_an_apk_fails_loudly_instead_of_shipping_a_stale_pin(self):
        with self.assertRaises(self.sync.ReleaseError):
            self.sync.describe(self.autowall, {"tag_name": "v3.0.0", "assets": []})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.sync.main(["--offline"]), 0)

    def test_workflow_keeps_the_page_in_sync(self):
        workflow = (ROOT / ".github/workflows/sync-release.yml").read_text(encoding="utf-8")
        self.assertIn("tools/sync_release.py", workflow)
        self.assertIn("--check", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn('["apps"]', workflow)


if __name__ == "__main__":
    unittest.main()

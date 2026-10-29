import base64
import hashlib
import json
import re
import struct
import unittest
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "https://free.justsimpleapps.online/"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading_one_count = 0
        self.images = []
        self.local_assets = []
        self.external_scripts = []
        self.inline_styles = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self.heading_one_count += 1
        if tag == "img":
            self.images.append(attrs)
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
        self.assertRegex(self.html, r"<title>[^<]{25,70}</title>")
        self.assertRegex(self.html, r'<meta name="description" content="[^"]{80,180}">')
        self.assertIn('<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">', self.html)
        self.assertEqual(self.parser.heading_one_count, 1, "Use exactly one descriptive H1")

    def test_open_graph_and_twitter_share_assets_exist(self):
        self.assertIn('property="og:url" content="https://free.justsimpleapps.online/"', self.html)
        self.assertIn('name="twitter:card" content="summary_large_image"', self.html)
        image = (ROOT / "assets/og-image.png").read_bytes()
        self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", image[16:24]), (1200, 630))
        self.assertEqual(self.parser.images, [
            {"src": "/assets/brand-mark.svg", "alt": "", "width": "42", "height": "42"},
            {"src": "/assets/brand-mark.svg", "alt": "", "width": "36", "height": "36"},
        ])

    def test_structured_data_matches_visible_faq_copy(self):
        graph = self.schema["@graph"]
        graph_types = {item["@type"] for item in graph}
        self.assertTrue({"Organization", "WebSite", "WebPage", "FAQPage"}.issubset(graph_types))
        faq = next(item for item in graph if item["@type"] == "FAQPage")
        self.assertEqual(len(faq["mainEntity"]), 5)
        for question in faq["mainEntity"]:
            self.assertIn(question["name"], self.visible_text)
            self.assertIn(question["acceptedAnswer"]["text"], self.visible_text)

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

    def test_static_assets_resolve_and_no_inline_or_external_runtime_code(self):
        self.assertEqual(self.parser.external_scripts, [], "The page should not depend on runtime scripts")
        self.assertEqual(self.parser.inline_styles, 0, "Styles must remain in the CSP-approved stylesheet")
        for asset in self.parser.local_assets:
            path = (ROOT / asset.lstrip("/")).resolve()
            self.assertTrue(path.is_relative_to(ROOT), f"Asset path escaped repo: {asset}")
            self.assertTrue(path.exists(), f"Missing local asset: {asset}")

    def test_404_is_noindex_and_returns_users_to_home(self):
        not_found = (ROOT / "404.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="robots" content="noindex, nofollow">', not_found)
        self.assertIn('href="/"', not_found)
        self.assertIn("Page not found", not_found)


if __name__ == "__main__":
    unittest.main()

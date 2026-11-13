"""Opt-in live smoke test for Browserless against the StreamLine listing.

Run with BROWSERLESS_API_TOKEN configured. This test uses Browserless' plain
Content API only; it does not enable stealth, proxies, or CAPTCHA solving.
"""

from __future__ import annotations

import os
import re
import unittest
from html import unescape

import requests
from bs4 import BeautifulSoup

from app.config import MAX_IMAGES
from app.streamline_parser import extract_streamline_images, parse_streamline_html


STREAMLINE_URL = (
    "https://streamlineautobg.com/car/2024-byd-han-ev-glory-edition-605km-fwd-"
    "01a1d3f0-e0c9-79cc-a65b-bae866d37132"
)
BROWSERLESS_CONTENT_URL = "https://production-sfo.browserless.io/content?timeout=60000"
BROWSERLESS_TOKEN = os.environ.get("BROWSERLESS_API_TOKEN")


def _looks_like_challenge(html: str, response_headers: dict[str, str]) -> bool:
    normalized_headers = {key.casefold(): value for key, value in response_headers.items()}
    if normalized_headers.get("cf-mitigated", "").casefold() == "challenge":
        return True
    excerpt = BeautifulSoup(html[:20000], "html.parser").get_text(" ", strip=True).casefold()
    return any(
        marker in excerpt
        for marker in ("just a moment", "enable javascript and cookies", "verify you are human")
    ) or "cf-chl-" in html[:20000].casefold()


@unittest.skipUnless(BROWSERLESS_TOKEN, "Set BROWSERLESS_API_TOKEN to run the live Browserless smoke test.")
class BrowserlessStreamlineLiveTests(unittest.TestCase):
    def test_browserless_returns_complete_streamline_listing_html(self):
        response = requests.post(
            BROWSERLESS_CONTENT_URL,
            headers={
                "Authorization": f"Bearer {BROWSERLESS_TOKEN}",
                "Cache-Control": "no-cache",
                "Content-Type": "application/json",
            },
            json={
                "url": STREAMLINE_URL,
                "gotoOptions": {"waitUntil": "domcontentloaded", "timeout": 45_000},
                "waitForSelector": {"selector": "main h1", "timeout": 15_000},
            },
            timeout=(10, 70),
        )
        self.assertEqual(
            response.status_code,
            200,
            f"Browserless Content API returned HTTP {response.status_code}; response body omitted.",
        )
        self.assertEqual(
            response.headers.get("X-Response-Code"),
            "200",
            f"Target page returned HTTP {response.headers.get('X-Response-Code')}; response body omitted.",
        )

        html = response.text
        self.assertFalse(
            _looks_like_challenge(html, dict(response.headers)),
            "Browserless returned a Cloudflare/access challenge, not the listing HTML.",
        )
        self.assertIn("Очаквана цена до България", html)

        vehicle = parse_streamline_html(html, STREAMLINE_URL)
        self.assertRegex(vehicle.estimated_price_display, r"\d[\d ]*\s*€")
        self.assertTrue(vehicle.title)
        self.assertIsNotNone(vehicle.year)

        main = BeautifulSoup(html, "html.parser").find("main")
        self.assertIsNotNone(main)
        first_photo = next(
            (
                re.fullmatch(r"Снимка\s+1\s+от\s+(\d+)", button.get("aria-label", ""), re.I)
                for button in main.find_all("button", attrs={"aria-label": True})
            ),
            None,
        )
        self.assertIsNotNone(first_photo, "The returned HTML has no listing gallery count.")
        gallery_count = int(first_photo.group(1))

        # Verify the full ordered gallery is present in the returned HTML,
        # independently of the app's intentional MAX_IMAGES display limit.
        normalized_html = unescape(html).replace("\\/", "/").replace("\\u002F", "/").replace('\\"', '"')
        all_image_urls = list(
            dict.fromkeys(
                re.findall(r'"hd"\s*:\s*"(https?://[^"\\]+)"', normalized_html, re.I)
            )
        )
        self.assertGreaterEqual(
            len(all_image_urls),
            gallery_count,
            f"Listing gallery advertises {gallery_count} photos but HTML contains only {len(all_image_urls)} full-size URLs.",
        )
        parsed_image_urls = extract_streamline_images(html)
        self.assertEqual(len(parsed_image_urls), min(gallery_count, MAX_IMAGES))
        self.assertEqual(parsed_image_urls, all_image_urls[: min(gallery_count, MAX_IMAGES)])

        print(
            "Browserless live listing verified: "
            f"title={vehicle.title!r}, year={vehicle.year}, "
            f"estimated_price={vehicle.estimated_price_display!r}, "
            f"gallery_urls={len(all_image_urls)}/{gallery_count}, "
            f"app_images={len(parsed_image_urls)}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

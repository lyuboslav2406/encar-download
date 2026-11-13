import unittest
from unittest.mock import patch

from app import generator
from app.streamline_parser import (
    build_streamline_post,
    extract_streamline_images,
    is_streamline_url,
    parse_streamline_html,
)
from app.vintrade_parser import is_vintrade_url


STREAMLINE_URL = "https://streamlineautobg.com/car/2025-byd-han-l-01a1d433-3a18-7e98-8403-d59774a0a910"


HTML = """<!doctype html><html lang="bg"><body><main>
<script type="application/ld+json">{"@type":"Car","name":"2025 BYD Han L","brand":{"name":"BYD"},"model":"Han L","offers":{"price":23834,"priceCurrency":"EUR"}}</script>
<h1>BYD Han L</h1>
<div class="price"><p>Цена</p><p>23&nbsp;834&nbsp;€</p><p><span>Очаквана цена до България</span><span>36&nbsp;380&nbsp;€</span></p></div>
<dl>
<dt>Година</dt><dd>2025</dd><dt>Пробег</dt><dd>28&nbsp;000 км</dd>
<dt>Гориво</dt><dd>Електрически</dd><dt>Мощност</dt><dd>1&nbsp;086 к.с.</dd>
<dt>Скорости</dt><dd>Автоматична</dd><dt>Задвижване</dt><dd>4x4 (постоянно)</dd>
<dt>Каросерия</dt><dd>Седан</dd><dt>Цвят</dt><dd>Сребрист</dd><dt>Електромотор</dt><dd>1&nbsp;087 к.с.</dd>
<dt>Батерия</dt><dd>83,2 kWh</dd><dt>Пробег на батерия</dt><dd>601 км (CLTC)</dd>
<dt>Бързо зареждане</dt><dd>6 мин.</dd>
</dl>
<section aria-label="Галерия">
<button aria-label="Снимка 1 от 3"><img src="https://erscglobal2.autoimg.cn/a/160x0_one.webp" srcset="https://erscglobal2.autoimg.cn/a/480x0_one.webp 480w, https://erscglobal2.autoimg.cn/a/1280x0_one.webp 1280w"></button>
<button aria-label="Снимка 2 от 3"><img src="https://erscglobal2.autoimg.cn/a/640x0_two.webp"></button>
<button aria-label="Снимка 3 от 3"><img src="https://erscglobal2.autoimg.cn/a/960x0_three.webp"></button>
</section>
<section aria-label="Подобни автомобили"><button aria-label="Снимка 1 от 1"><img src="https://erscglobal2.autoimg.cn/a/640x0_similar.webp"></button></section>
</main></body></html>"""


class StreamlineParserTests(unittest.TestCase):
    def test_detects_listing_domain_and_path_only(self):
        self.assertTrue(is_streamline_url(STREAMLINE_URL))
        self.assertTrue(is_streamline_url(STREAMLINE_URL.replace("streamlineautobg.com", "www.streamlineautobg.com")))
        self.assertFalse(is_streamline_url("https://evil.example/car/2025-test"))
        self.assertFalse(is_streamline_url("https://streamlineautobg.com/cars/2025-test"))
        self.assertFalse(is_streamline_url("https://streamlineautobg.com.evil.example/car/2025-test"))
        self.assertFalse(is_streamline_url("https://www.encar.com/car/2025-test"))
        self.assertTrue(is_vintrade_url("https://vintrade.up.railway.app/car/example"))

    def test_parses_listing_fields_direct_price_and_post(self):
        vehicle = parse_streamline_html(HTML, STREAMLINE_URL)
        self.assertEqual(vehicle.make, "BYD")
        self.assertEqual(vehicle.model, "Han L")
        self.assertEqual(vehicle.title, "BYD Han L")
        self.assertEqual(vehicle.year, 2025)
        self.assertEqual(vehicle.mileage_km, 28000)
        self.assertEqual(vehicle.fuel_type, "Електрически")
        self.assertEqual(vehicle.transmission, "Автоматична")
        self.assertEqual(vehicle.engine, "1 087 к.с.")
        self.assertEqual(vehicle.specifications["Батерия"], "83,2 kWh")
        self.assertEqual(vehicle.estimated_price_display, "36 380 €")
        self.assertEqual(
            vehicle.image_urls,
            [
                "https://erscglobal2.autoimg.cn/a/1280x0_one.webp",
                "https://erscglobal2.autoimg.cn/a/640x0_two.webp",
                "https://erscglobal2.autoimg.cn/a/960x0_three.webp",
            ],
        )

        post, summary = build_streamline_post(vehicle)
        self.assertTrue(post.startswith("💥 КРАЙНА ЦЕНА ДО БЪЛГАРИЯ: 36 380 € 💥"))
        self.assertIn("🚙 BYD Han L 🚙", post)
        self.assertIn("2025 • 🖤 28 000 KM", post)
        self.assertIn("⛽ Електрически | ⚙️ Автоматична", post)
        self.assertIn("💎 4x4 (постоянно) | Седан", post)
        self.assertIn("Батерия: 83,2 kWh", post)
        self.assertNotRegex(post, r"━+\n━+")
        self.assertNotRegex(post, r"(?i)steering|hand drive|волан|руль")
        self.assertNotRegex(post, r"(?i)viber|11MsM")
        self.assertIn("0877 56 77 52", post)
        self.assertIn("0878 588 266", post)
        self.assertNotIn("23 834", post)
        self.assertIn("Прогнозна цена според обявата: 36 380 €", summary)
        self.assertNotIn("курс", summary.lower())

    def test_streamline_post_omits_steering_position_fields_and_values(self):
        vehicle = parse_streamline_html(HTML, STREAMLINE_URL)
        vehicle.specifications["Задвижване"] = "Ляв волан"
        vehicle.specifications["Волан"] = "Десен волан"
        vehicle.specifications["Steering wheel"] = "Right-hand drive"
        post, _ = build_streamline_post(vehicle)
        self.assertNotRegex(post, r"(?i)steering|hand drive|волан|руль")
        self.assertIn("Батерия: 83,2 kWh", post)
        self.assertNotRegex(post, r"━+\n━+")

    def test_estimated_price_is_required(self):
        html_without_estimate = HTML.replace(
            "<span>Очаквана цена до България</span><span>36&nbsp;380&nbsp;€</span>",
            "<span>Цена по запитване</span>",
        )
        with self.assertRaisesRegex(ValueError, "прогнозната цена"):
            parse_streamline_html(html_without_estimate, STREAMLINE_URL)

    def test_accepts_alternate_forecast_label(self):
        html = HTML.replace("Очаквана цена до България", "Прогнозна цена")
        vehicle = parse_streamline_html(html, STREAMLINE_URL)
        self.assertEqual(vehicle.estimated_price_display, "36 380 €")

    def test_prefers_complete_ordered_serialized_gallery(self):
        gallery = ''.join(
            f'{{"hd":"https://erscglobal2.autoimg.cn/a/1400x0_photo-{index}.webp"}}'
            for index in range(1, 4)
        )
        html = HTML.replace("</main>", f'<script>self.__next_f.push([1,"{gallery}"])</script></main>')
        self.assertEqual(
            extract_streamline_images(html),
            [
                "https://erscglobal2.autoimg.cn/a/1400x0_photo-1.webp",
                "https://erscglobal2.autoimg.cn/a/1400x0_photo-2.webp",
                "https://erscglobal2.autoimg.cn/a/1400x0_photo-3.webp",
            ],
        )

    def test_gallery_respects_existing_fifteen_image_limit(self):
        gallery = ''.join(
            f'{{"hd":"https://erscglobal2.autoimg.cn/a/1400x0_photo-{index}.webp"}}'
            for index in range(1, 28)
        )
        html = HTML.replace("от 3", "от 27").replace("</main>", f'<script>self.__next_f.push([1,"{gallery}"])</script></main>')
        images = extract_streamline_images(html)
        self.assertEqual(len(images), 15)
        self.assertIn("photo-1.webp", images[0])
        self.assertIn("photo-15.webp", images[-1])

    def test_price_summary_dispatches_without_conversion(self):
        with (
            patch.object(generator, "fetch_streamline_html", return_value=HTML),
            patch.object(generator, "get_eur_to_krw_rate_info") as exchange_rate,
            patch.object(generator, "calculate_final_price_eur") as extra_costs,
        ):
            result = generator.process_price_summary(STREAMLINE_URL)
        self.assertEqual(result["source"], "streamline")
        self.assertIn("36 380 €", result["price_summary"])
        self.assertIsNone(result["exchange_rate"])
        exchange_rate.assert_not_called()
        extra_costs.assert_not_called()


if __name__ == "__main__":
    unittest.main()

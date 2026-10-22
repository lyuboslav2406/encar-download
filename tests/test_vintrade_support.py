import tempfile
import time
import unittest
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from starlette.requests import Request

from app import generator, routes
from app.vintrade_parser import (
    build_vintrade_post,
    download_vintrade_images,
    extract_gallery_images,
    is_vintrade_url,
    parse_vintrade_html,
)


VINTRADE_URL = "https://vintrade.up.railway.app/car/01a1585b-8916-7f13-95a6-255d04e48223"


HTML = """<!doctype html><html><body><main>
<region aria-label="2026 Audi A6L e-tron">
<img alt="Photo 1 of 2" src="https://erscglobal2.autoimg.cn/a/640x0_photo-one.jpg.webp"
 srcset="https://erscglobal2.autoimg.cn/a/640x0_photo-one.jpg.webp 640w, https://erscglobal2.autoimg.cn/a/1280x0_photo-one.jpg.webp 1280w">
<img alt="Photo 2 of 2" src="https://erscglobal2.autoimg.cn/a/640x0_photo-two.jpg.webp">
</region>
<h1>2026 Audi A6L e-tron</h1><p>Model Pioneer Edition</p>
<dl><dt>Powertrain</dt><dd>Electric</dd><dt>Power</dt><dd>349 hp</dd>
<dt>Gearbox</dt><dd>Automatic</dd><dt>Drive</dt><dd>RWD</dd>
<dt>Battery</dt><dd>107 kWh</dd><dt>Electric range</dt><dd>745 km · CLTC</dd>
<dt>Body style</dt><dd>Sedan</dd><dt>Odometer</dt><dd>4,400 km</dd><dt>Photos</dt><dd>2</dd></dl>
<aside><p>Asking price in China</p><p>€33,817</p><p>$37,960</p><p>Rate on 19.10.2026: €1 = $1.1225</p>
<dl><dt>Car price</dt><dd>€33,817</dd><dt>Taxes to Bulgaria</dt><dd>≈ €10,858</dd></dl>
<p>Estimated price €44,675</p></aside>
<script>self.__next_f.push([1,"{\\\"hd\\\":\\\"https://erscglobal2.autoimg.cn/a/1280x0_photo-one.jpg.webp\\\",\\\"thumb\\\":\\\"https://erscglobal2.autoimg.cn/a/640x480_photo-one.jpg.webp\\\"},{\\\"hd\\\":\\\"https://erscglobal2.autoimg.cn/a/1280x0_photo-two.jpg.webp\\\",\\\"thumb\\\":\\\"https://erscglobal2.autoimg.cn/a/640x480_photo-two.jpg.webp\\\"},{\\\"hd\\\":\\\"https://erscglobal2.autoimg.cn/a/1280x0_similar-car.jpg.webp\\\"}"])</script>
<h2>Similar cars</h2><img src="https://erscglobal2.autoimg.cn/a/640x0_similar-car.jpg.webp">
</main></body></html>"""


class VinTradeParserTests(unittest.TestCase):
    def test_detects_only_vintrade_host(self):
        self.assertTrue(is_vintrade_url(VINTRADE_URL))
        self.assertFalse(is_vintrade_url("https://evil.example/car/01a"))
        self.assertFalse(is_vintrade_url("https://vintrade.up.railway.app.evil.example/car/01a"))

    def test_parses_verified_details_prices_and_deduplicated_gallery(self):
        vehicle = parse_vintrade_html(HTML, VINTRADE_URL)
        self.assertEqual(vehicle.title, "2026 Audi A6L e-tron")
        self.assertEqual(vehicle.year, 2026)
        self.assertEqual(vehicle.mileage_km, 4400)
        self.assertEqual(vehicle.specifications["Battery"], "107 kWh")
        self.assertEqual(vehicle.prices["asking"], {"amount": 33817, "currency": "€"})
        self.assertEqual(vehicle.prices["asking_usd"], {"amount": 37960, "currency": "$"})
        self.assertEqual(vehicle.prices["eur_usd_rate"], {"date": "19.10.2026", "rate": 1.1225})
        self.assertEqual(vehicle.prices["taxes_to_bulgaria"], {"amount": 10858, "currency": "€"})
        self.assertEqual(vehicle.prices["estimated_bulgaria"], {"amount": 44675, "currency": "€"})
        self.assertEqual(len(vehicle.image_urls), 2)
        self.assertIn("1280x0_photo-one", vehicle.image_urls[0])
        self.assertNotIn("similar-car", " ".join(vehicle.image_urls))

    def test_missing_prices_and_specs_are_not_invented_or_calculated(self):
        html = '<main><h1>Unknown Car</h1><p>Asking price on request</p></main>'
        vehicle = parse_vintrade_html(html, VINTRADE_URL)
        post, summary = build_vintrade_post(vehicle)
        self.assertIsNone(vehicle.year)
        self.assertIsNone(vehicle.mileage_km)
        self.assertIsNone(vehicle.prices["asking"])
        self.assertIsNone(vehicle.prices["taxes_to_bulgaria"])
        self.assertIsNone(vehicle.prices["estimated_bulgaria"])
        self.assertIn("Крайна цена не е изчислена", summary)
        self.assertNotIn("КРАЙНА ЦЕНА ДО БЪЛГАРИЯ:", post)
        self.assertNotIn("Бензин", post)
        self.assertNotIn("Автоматик", post)
        self.assertNotIn("VIN проверка", post)

    def test_webp_download_is_converted_to_jpeg(self):
        buffer = BytesIO()
        Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(buffer, format="WEBP")
        response = type("Response", (), {"content": buffer.getvalue(), "raise_for_status": lambda self: None})()
        with tempfile.TemporaryDirectory() as temp_dir, patch("app.vintrade_parser.requests.get", return_value=response):
            files = download_vintrade_images(["https://example/photo.webp"], Path(temp_dir))
            self.assertEqual([path.name for path in files], ["01.jpg"])
            with Image.open(files[0]) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.mode, "RGB")


class VinTradeJobWorkflowTests(unittest.TestCase):
    def test_batch_accepts_mixed_source_urls(self):
        encar_url = "https://www.encar.com/dc/dc_cardetailview.do?carid=123"
        with routes._jobs_lock:
            prior_ids = set(routes._jobs)
        with patch.object(routes._executor, "submit") as submit:
            response = routes.batch_generate(None, {"urls": [encar_url, VINTRADE_URL]})
        try:
            self.assertEqual(len(response["job_ids"]), 2)
            self.assertEqual(submit.call_count, 2)
            with routes._jobs_lock:
                jobs = [routes._jobs[job_id] for job_id in response["job_ids"]]
            self.assertEqual([job.encar_url for job in jobs], [encar_url, VINTRADE_URL])
            self.assertTrue(all(job.status == routes.JobStatus.QUEUED for job in jobs))
        finally:
            with routes._jobs_lock:
                for job_id in set(routes._jobs) - prior_ids:
                    routes._jobs.pop(job_id, None)

    def test_vintrade_job_reuses_gallery_publish_and_schedule_order(self):
        job_id = "8f67305e-f8af-4aaa-9362-949bdd79da97"
        image_ids = ["02.jpg", "01.jpg"]
        request = Request({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "https", "path": "/publish-facebook",
            "raw_path": b"/publish-facebook", "query_string": b"", "headers": [],
            "client": ("127.0.0.1", 12345), "server": ("example.test", 443),
        })
        success = {"data": {"createPost": {"post": {"id": "mock-post"}}}}

        def fake_download(urls, job_dir):
            paths = []
            for index, _ in enumerate(urls, 1):
                path = Path(job_dir) / f"{index:02d}.jpg"
                path.write_bytes(b"jpeg")
                paths.append(path)
            return paths

        with tempfile.TemporaryDirectory() as temp_dir:
            generated = Path(temp_dir)
            with ExitStack() as stack:
                stack.enter_context(patch.object(generator, "GENERATED_DIR", generated))
                stack.enter_context(patch.object(generator, "cleanup_old_jobs"))
                stack.enter_context(patch.object(generator, "fetch_vintrade_html", return_value=HTML))
                stack.enter_context(patch.object(generator, "download_vintrade_images", side_effect=fake_download))
                stack.enter_context(patch.object(generator, "create_zip"))
                stack.enter_context(patch.object(routes, "GENERATED_DIR", generated))
                result = generator.process_encar(VINTRADE_URL, job_id=job_id)

                self.assertEqual(result["job_id"], job_id)
                self.assertEqual(result["source"], "vintrade")
                self.assertEqual(result["images_count"], 2)
                self.assertTrue((generated / job_id / "detail_page.html").exists())
                self.assertEqual([p.name for p in sorted((generated / job_id).glob("*.jpg"))], ["01.jpg", "02.jpg"])
                gallery = routes.get_photos(job_id, request)
                self.assertEqual([url.rsplit("/", 1)[-1] for url in gallery["image_urls"]], ["01.jpg", "02.jpg"])

                with (
                    patch.object(routes, "validate_buffer_credentials", return_value=("key", "channel")),
                    patch.object(routes, "create_media_token", return_value="signed"),
                    patch.object(routes, "call_buffer_graphql", return_value=success) as publish,
                ):
                    published = routes.publish_facebook(request, {"job_id": job_id, "image_ids": image_ids, "message": "post"})
                self.assertTrue(published["success"])
                publish_assets = publish.call_args.args[2]["input"]["assets"]
                self.assertEqual([asset["image"]["url"].rsplit("/", 1)[-1] for asset in publish_assets], image_ids)

                ordered_r2 = [f"https://r2.example/{name}" for name in image_ids]
                with (
                    patch.object(routes, "validate_buffer_credentials", return_value=("key", "channel")),
                    patch.object(routes, "upload_scheduled_images_to_r2", return_value=ordered_r2) as upload,
                    patch.object(routes, "call_buffer_graphql", return_value=success) as schedule,
                ):
                    scheduled = routes.schedule_facebook(request, {
                        "job_id": job_id, "image_ids": image_ids, "message": "post",
                        "scheduled_publish_time": int(time.time()) + 3600,
                    })
                self.assertTrue(scheduled["success"])
                upload.assert_called_once_with(job_id, image_ids)
                schedule_assets = schedule.call_args.args[2]["input"]["assets"]
                self.assertEqual([asset["image"]["url"] for asset in schedule_assets], ordered_r2)


if __name__ == "__main__":
    unittest.main()

import tempfile
import threading
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
    get_vintrade_vehicle_title,
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
<dt>Body style</dt><dd>Sedan</dd><dt>Trim</dt><dd>Model Pioneer Edition</dd>
<dt>Odometer</dt><dd>4,400 km</dd><dt>Photos</dt><dd>2</dd></dl>
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
        post, _ = build_vintrade_post(vehicle)
        self.assertIn("💥 КРАЙНА ЦЕНА ДО БЪЛГАРИЯ: 44 675 € 💥", post)
        self.assertNotIn("Ориентировъчната цена е посочена", post)
        self.assertEqual(get_vintrade_vehicle_title(vehicle), "Audi A6L e-tron Pioneer Edition — 2026")

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
    def test_encar_result_exposes_generated_vehicle_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(generator, "GENERATED_DIR", Path(temp_dir)),
                patch.object(generator, "cleanup_old_jobs"),
                patch.object(generator, "download_html", return_value="<html></html>"),
                patch.object(generator, "extract_price_krw", return_value=1_000_000),
                patch.object(generator, "extract_year", return_value=2022),
                patch.object(generator, "extract_mileage", return_value=20_000),
                patch.object(generator, "get_eur_to_krw_rate_info", return_value=(1_700.0, "2026-10-20")),
                patch.object(generator, "krw_to_eur_with_rate", return_value=1_000),
                patch.object(generator, "calculate_final_price_eur", return_value=(9_000, 8_000)),
                patch.object(generator, "format_eur", side_effect=lambda value: str(value)),
                patch.object(generator, "format_km", side_effect=lambda value: str(value)),
                patch.object(generator, "extract_clean_car_text", return_value="verified listing text"),
                patch.object(generator, "generate_facebook_data_with_openai", return_value={"title": "Audi Q4 e-tron 40"}),
                patch.object(generator, "build_facebook_post", return_value="generated post"),
                patch.object(generator, "download_images", return_value=[]),
                patch.object(generator, "create_zip"),
            ):
                result = generator.process_encar("https://www.encar.com/car/test", job_id="encar-title-test")
        self.assertEqual(result["vehicle_title"], "Audi Q4 e-tron 40 — 2022")

    def test_remove_poll_add_and_seven_car_limit_recovery(self):
        def submit(urls):
            with patch.object(routes._executor, "submit"):
                return routes.batch_generate(None, {"urls": urls})["job_ids"]

        first_id = submit(["https://vintrade.up.railway.app/car/first"])[0]
        self.assertTrue(routes.remove_batch_job(first_id)["removed"])
        self.assertNotIn(first_id, [job["job_id"] for job in routes.batch_status(None)["jobs"]])
        replacement = submit(["https://www.encar.com/car/replacement"])
        self.assertEqual(len(replacement), 1)
        routes.remove_batch_job(replacement[0])

        seven_ids = submit([f"https://example.test/car/{index}" for index in range(7)])
        self.assertEqual(len(seven_ids), 7)
        with self.assertRaises(routes.HTTPException) as error:
            submit(["https://example.test/car/overflow"])
        self.assertEqual(error.exception.status_code, 409)
        for job_id in seven_ids:
            routes.remove_batch_job(job_id)
        second_seven = submit([f"https://example.test/car/new-{index}" for index in range(7)])
        self.assertEqual(len(second_seven), 7)
        for job_id in second_seven:
            routes.remove_batch_job(job_id)

    def test_removing_processing_job_prevents_worker_resurrection(self):
        job_id = "4a9652ec-7333-4428-8f1c-b92cc4a9a12f"
        started = threading.Event()
        release = threading.Event()
        with routes._jobs_lock:
            routes._jobs[job_id] = routes.Job(job_id, "https://example.test/car", routes.JobStatus.QUEUED)

        def slow_process(*_args, **_kwargs):
            started.set()
            release.wait(timeout=5)
            return {"job_id": job_id, "images_count": 0}

        with patch.object(routes, "process_encar", side_effect=slow_process):
            worker = threading.Thread(target=routes._process_job_background, args=(job_id, "https://example.test/car"))
            worker.start()
            self.assertTrue(started.wait(timeout=2))
            self.assertEqual(routes._jobs[job_id].status, routes.JobStatus.PROCESSING)
            routes.remove_batch_job(job_id)
            release.set()
            worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertNotIn(job_id, routes._jobs)
        self.assertEqual(routes.batch_status(None)["jobs"], [])

    def test_removing_one_registry_job_preserves_other_job_state(self):
        first_id, second_id = "job-one", "job-two"
        other = routes.Job(second_id, "url-two", routes.JobStatus.COMPLETED, result={"facebook_post": "draft", "image_ids": ["02.jpg", "01.jpg"]})
        with routes._jobs_lock:
            routes._jobs[first_id] = routes.Job(first_id, "url-one", routes.JobStatus.FAILED)
            routes._jobs[second_id] = other
        try:
            routes.remove_batch_job(first_id)
            self.assertIs(routes._jobs[second_id], other)
            self.assertEqual(routes._jobs[second_id].result, {"facebook_post": "draft", "image_ids": ["02.jpg", "01.jpg"]})
        finally:
            with routes._jobs_lock:
                routes._jobs.pop(first_id, None)
                routes._jobs.pop(second_id, None)

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

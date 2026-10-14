import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request

from app import generator, routes


class BatchJobImagePathTests(unittest.TestCase):
    def test_batch_job_directory_is_used_by_photos_publish_and_schedule(self):
        job_id = "8f67305e-f8af-4aaa-9362-949bdd79da97"
        image_ids = ["01.jpg", "02.jpg", "03.jpg"]
        success_response = {"data": {"createPost": {"post": {"id": "post-123"}}}}

        def fake_download_images(_html, job_dir):
            paths = []
            for image_name in image_ids:
                image_path = Path(job_dir) / image_name
                image_path.write_bytes(b"image")
                paths.append(image_path)
            return paths

        request = Request({
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/publish-facebook",
            "raw_path": b"/publish-facebook",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("example.test", 443),
        })

        with tempfile.TemporaryDirectory() as temp_dir:
            generated_dir = Path(temp_dir)
            with ExitStack() as patch_stack:
                for patcher in (
                    patch.object(generator, "GENERATED_DIR", generated_dir),
                    patch.object(routes, "GENERATED_DIR", generated_dir),
                    patch.object(generator, "cleanup_old_jobs"),
                    patch.object(generator, "download_html", return_value="<html></html>"),
                    patch.object(generator, "extract_price_krw", return_value=1_000_000),
                    patch.object(generator, "extract_year", return_value=2020),
                    patch.object(generator, "extract_mileage", return_value=10_000),
                    patch.object(generator, "get_eur_to_krw_rate_info", return_value=(1_700.0, "2026-10-14")),
                    patch.object(generator, "krw_to_eur_with_rate", return_value=1_000),
                    patch.object(generator, "calculate_final_price_eur", return_value=(2_000, 1_000)),
                    patch.object(generator, "format_eur", side_effect=lambda value: str(value)),
                    patch.object(generator, "format_km", side_effect=lambda value: str(value)),
                    patch.object(generator, "extract_clean_car_text", return_value="vehicle"),
                    patch.object(generator, "generate_facebook_data_with_openai", return_value={}),
                    patch.object(generator, "build_facebook_post", return_value="Facebook post"),
                    patch.object(generator, "download_images", side_effect=fake_download_images),
                    patch.object(generator, "create_zip"),
                ):
                    patch_stack.enter_context(patcher)
                with routes._jobs_lock:
                    routes._jobs[job_id] = routes.Job(
                        job_id=job_id,
                        encar_url="https://example.test/car/1",
                        status=routes.JobStatus.QUEUED,
                    )
                try:
                    routes._process_job_background(job_id, "https://example.test/car/1")
                    with routes._jobs_lock:
                        job = routes._jobs[job_id]
                        result = job.result

                    self.assertEqual(job.status, routes.JobStatus.COMPLETED)
                    self.assertEqual(result["job_id"], job_id)
                    self.assertEqual(result["photos_url"], f"/photos/{job_id}")
                    job_dir = generated_dir / job_id
                    self.assertTrue(job_dir.is_dir())
                    self.assertEqual(
                        sorted(path.name for path in job_dir.glob("*.jpg")),
                        image_ids,
                    )
                    photos_result = routes.get_photos(job_id, request)
                    self.assertEqual(photos_result["job_id"], job_id)
                    self.assertEqual(photos_result["images_count"], len(image_ids))
                    self.assertEqual(
                        [url.rsplit("/", 1)[-1] for url in photos_result["image_urls"]],
                        image_ids,
                    )

                    with (
                        patch.object(routes, "validate_buffer_credentials", return_value=("key", "channel")),
                        patch.object(routes, "create_media_token", return_value="media-token"),
                        patch.object(routes, "call_buffer_graphql", return_value=success_response) as publish_gql,
                    ):
                        publish_result = routes.publish_facebook(
                            request,
                            {"job_id": job_id, "image_ids": image_ids, "message": "post"},
                        )

                    self.assertTrue(publish_result["success"])
                    publish_assets = publish_gql.call_args.args[2]["input"]["assets"]
                    self.assertEqual(
                        [asset["image"]["url"].rsplit("/", 1)[-1] for asset in publish_assets],
                        image_ids,
                    )
                    self.assertTrue(all(f"/buffer-media/media-token/{name}" in asset["image"]["url"]
                                        for name, asset in zip(image_ids, publish_assets)))

                    r2_urls = [f"https://r2.example/scheduled/{job_id}/{name}" for name in image_ids]
                    with (
                        patch.object(routes, "validate_buffer_credentials", return_value=("key", "channel")),
                        patch.object(routes, "upload_scheduled_images_to_r2", return_value=r2_urls) as upload_images,
                        patch.object(routes, "call_buffer_graphql", return_value=success_response) as schedule_gql,
                    ):
                        schedule_result = routes.schedule_facebook(
                            request,
                            {
                                "job_id": job_id,
                                "image_ids": image_ids,
                                "message": "post",
                                "scheduled_publish_time": int(time.time()) + 3600,
                            },
                        )

                    self.assertTrue(schedule_result["success"])
                    upload_images.assert_called_once_with(job_id, image_ids)
                    schedule_assets = schedule_gql.call_args.args[2]["input"]["assets"]
                    self.assertEqual(
                        [asset["image"]["url"] for asset in schedule_assets],
                        r2_urls,
                    )
                finally:
                    with routes._jobs_lock:
                        routes._jobs.pop(job_id, None)


if __name__ == "__main__":
    unittest.main()

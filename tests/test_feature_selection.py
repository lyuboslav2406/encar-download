import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import STATIC_FOOTER
from app.legacy_post_generation import apply_legacy_fallbacks_and_filters
from app.openai_service import build_facebook_post, generate_facebook_data_with_openai
from app.scraper import extract_clean_car_text

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "external-script" / "encar_download2.py"


def load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LegacyPostGenerationTests(unittest.TestCase):
    def test_extract_clean_car_text_keeps_old_visibility_rules_and_limit(self):
        html = """
        <html><head><style>.x{color:red;}</style><script>var x=1;</script></head>
        <body>
          <noscript>hidden</noscript>
          <svg><text>shape</text></svg>
          <div>Visible title</div>
          <div>Visible line</div>
        </body></html>
        """
        text = extract_clean_car_text(html)
        self.assertIn("Visible title", text)
        self.assertIn("Visible line", text)
        self.assertNotIn("var x=1", text)
        self.assertNotIn("hidden", text)
        self.assertLessEqual(len(text), 12000)

    def test_old_schema_json_is_accepted(self):
        car_context = {
            "year": 2023,
            "mileage": 54736,
            "final_price_eur": 64000,
            "raw_car_text": "Burmester\nAIRMATIC\nHUD",
        }
        model_response = {
            "title": "Mercedes-Benz GLE 300d 4MATIC",
            "fuel": "Дизел",
            "transmission": "Автоматик",
            "short_accent": "AIRMATIC | Burmester | Head-up",
            "strong_highlights": ["AIRMATIC", "Burmester", "Head-up дисплей"],
            "facebook_post": "",
        }

        class FakeResponses:
            @staticmethod
            def create(model, input):
                del model
                assert "ТЕКСТ ОТ ОБЯВАТА" in input
                return type("R", (), {"output_text": json.dumps(model_response, ensure_ascii=False)})()

        with patch("app.openai_service.client", type("C", (), {"responses": FakeResponses()})()):
            result = generate_facebook_data_with_openai(car_context)

        self.assertEqual(result["title"], "Mercedes-Benz GLE 300d 4MATIC")
        self.assertEqual(result["fuel"], "Дизел")
        self.assertEqual(result["transmission"], "Автоматик")
        self.assertIn("strong_highlights", result)

    def test_weak_feature_filtering_matches_old_behavior(self):
        filtered = apply_legacy_fallbacks_and_filters(
            {
                "title": "X",
                "fuel": "gasoline",
                "transmission": "",
                "short_accent": "a | b | c",
                "strong_highlights": [
                    "LED фарове",
                    "Парктроник",
                    "Климатик",
                    "Задна камера",
                    "Burmester",
                    "AIRMATIC",
                ],
            }
        )

        self.assertEqual(filtered["fuel"], "Бензин")
        self.assertEqual(filtered["transmission"], "Автоматик")
        self.assertIn("Burmester", filtered["strong_highlights"])
        self.assertIn("AIRMATIC", filtered["strong_highlights"])
        self.assertNotIn("LED фарове", filtered["strong_highlights"])
        self.assertNotIn("Парктроник", filtered["strong_highlights"])

    def test_build_facebook_post_renders_six_highlights_and_footer(self):
        car_context = {"year": 2023, "mileage": 54736, "final_price_eur": 64000}
        data = {
            "title": "Mercedes-Benz GLE 300d 4MATIC (W167)",
            "fuel": "Дизел",
            "transmission": "Автоматик",
            "short_accent": "AIRMATIC | Burmester | 360° камера",
            "strong_highlights": ["AIRMATIC"],
        }

        post = build_facebook_post(car_context, data)
        checklist = [line for line in post.splitlines() if line.startswith("✅ ")]

        self.assertEqual(len(checklist), 10)
        self.assertTrue(post.endswith(STATIC_FOOTER))

    def test_app_and_standalone_render_same_post_body(self):
        car_context = {"year": 2023, "mileage": 54736, "final_price_eur": 64000}
        data = {
            "title": "Mercedes-Benz GLE 300d 4MATIC (W167)",
            "fuel": "Дизел",
            "transmission": "Автоматик",
            "short_accent": "AIRMATIC | Burmester | 360° камера",
            "strong_highlights": ["AIRMATIC", "Burmester", "360° камера"],
        }

        app_post = build_facebook_post(car_context, dict(data))

        original_api_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = original_api_key or "test-key"
        try:
            module = load_module_from_path("encar_download2_legacy_parity", SCRIPT_PATH)
            standalone_body = module.build_facebook_post(car_context, dict(data))
            standalone_post = standalone_body.rstrip()
            while standalone_post.endswith("━━━━━━━━━━━━━━━━━━━"):
                standalone_post = standalone_post[:-19].rstrip()
            standalone_post = standalone_post + "\n" + module.STATIC_FOOTER
        finally:
            if original_api_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = original_api_key

        self.assertEqual(app_post, standalone_post)


if __name__ == "__main__":
    unittest.main()

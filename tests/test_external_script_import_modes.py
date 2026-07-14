import importlib.util
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "external-script" / "encar_download2.py"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExternalScriptImportModeTests(unittest.TestCase):
    @staticmethod
    def valid_payload(rate=1700.0):
        return {
            "date": "2026-07-13",
            "base": "EUR",
            "quote": "KRW",
            "rate": rate,
        }

    def test_repository_mode_uses_imported_app_pricing(self):
        fake_app = types.ModuleType("app")
        fake_pricing = types.ModuleType("app.pricing")

        class FakeExchangeRateError(ValueError):
            pass

        def fake_get_eur_to_krw_rate_info():
            return 1800.0, "2026-07-13"

        def fake_krw_to_eur_with_rate(krw_price, krw_per_eur):
            return float(krw_price) / float(krw_per_eur)

        fake_pricing.FRANKFURTER_SOURCE = "Frankfurter"
        fake_pricing.ExchangeRateError = FakeExchangeRateError
        fake_pricing.get_eur_to_krw_rate_info = fake_get_eur_to_krw_rate_info
        fake_pricing.krw_to_eur_with_rate = fake_krw_to_eur_with_rate

        original_api_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-key"

        try:
            with patch.dict(
                sys.modules,
                {
                    "app": fake_app,
                    "app.pricing": fake_pricing,
                },
                clear=False,
            ):
                module = load_module_from_path("encar_download2_repo_mode", SCRIPT_PATH)

            self.assertIs(module.get_eur_to_krw_rate_info, fake_get_eur_to_krw_rate_info)
            self.assertIs(module.krw_to_eur_with_rate, fake_krw_to_eur_with_rate)
            self.assertIs(module.ExchangeRateError, FakeExchangeRateError)
            self.assertEqual(module.FRANKFURTER_SOURCE, "Frankfurter")
        finally:
            if original_api_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = original_api_key

    def test_standalone_mode_loads_fallback_and_converts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_script = Path(temp_dir) / "encar_download2.py"
            shutil.copy2(SCRIPT_PATH, temp_script)

            original_api_key = os.environ.get("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = "test-key"

            original_sys_path = list(sys.path)
            filtered_sys_path = [
                p for p in original_sys_path
                if p not in {"", str(REPO_ROOT), str(Path.cwd())}
            ]

            try:
                with patch.dict(sys.modules, {}, clear=False):
                    sys.modules.pop("app", None)
                    sys.modules.pop("app.pricing", None)
                    with patch.object(sys, "path", filtered_sys_path):
                        module = load_module_from_path("encar_download2_standalone", temp_script)

                self.assertTrue(issubclass(module.ExchangeRateError, ValueError))

                with patch.object(module.requests, "get", return_value=FakeResponse(self.valid_payload(rate=1700.0))):
                    krw_per_eur, rate_date = module.get_eur_to_krw_rate_info()

                self.assertEqual(krw_per_eur, 1700.0)
                self.assertEqual(rate_date, "2026-07-13")
                converted = module.krw_to_eur_with_rate(39_900_000, krw_per_eur)
                self.assertAlmostEqual(converted, 23_470.588, places=3)
            finally:
                if original_api_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = original_api_key

    def test_standalone_fallback_rejects_invalid_provider_responses(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_script = Path(temp_dir) / "encar_download2.py"
            shutil.copy2(SCRIPT_PATH, temp_script)

            original_api_key = os.environ.get("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = "test-key"

            original_sys_path = list(sys.path)
            filtered_sys_path = [
                p for p in original_sys_path
                if p not in {"", str(REPO_ROOT), str(Path.cwd())}
            ]

            try:
                with patch.dict(sys.modules, {}, clear=False):
                    sys.modules.pop("app", None)
                    sys.modules.pop("app.pricing", None)
                    with patch.object(sys, "path", filtered_sys_path):
                        module = load_module_from_path("encar_download2_standalone_invalid", temp_script)

                invalid_payloads = [
                    [self.valid_payload(rate=1700.0)],
                    {"date": "2026-07-13", "base": "EUR", "quote": "KRW"},
                    {"date": "2026-07-13", "base": "USD", "quote": "KRW", "rate": 1700.0},
                    {"date": "2026-07-13", "base": "EUR", "quote": "JPY", "rate": 1700.0},
                    self.valid_payload(rate=True),
                    self.valid_payload(rate="bad"),
                    self.valid_payload(rate=float("nan")),
                    self.valid_payload(rate=float("inf")),
                    self.valid_payload(rate=0),
                    self.valid_payload(rate=-10),
                    self.valid_payload(rate=100),
                    self.valid_payload(rate=10000),
                ]

                for payload in invalid_payloads:
                    with self.subTest(payload=payload):
                        with patch.object(module.requests, "get", return_value=FakeResponse(payload)):
                            with self.assertRaises(module.ExchangeRateError):
                                module.get_eur_to_krw_rate_info()
            finally:
                if original_api_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = original_api_key


if __name__ == "__main__":
    unittest.main()

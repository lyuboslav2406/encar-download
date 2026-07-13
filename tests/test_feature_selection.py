import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.feature_selection import (
    build_option_evidence_block,
    flatten_validated_features,
    validate_ai_feature_selection,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "external-script" / "encar_download2.py"


def load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FeatureSelectionTests(unittest.TestCase):
    def test_unknown_but_valuable_features_reach_ai_prompt_evidence_block(self):
        raw = """
        Executive Rear Seat Package
        Crystal headlights
        Digital Key Plus
        """
        block = build_option_evidence_block(raw)
        self.assertIn("Executive Rear Seat Package", block)

    def test_unknown_feature_is_not_rejected_by_closed_whitelist(self):
        raw = """
        Executive Rear Seat Package
        Crystal headlights
        """
        payload = {
            "headline_features": [
                {
                    "source_feature": "Executive Rear Seat Package",
                    "display_name_bg": "Executive Rear Seat Package",
                    "reason": "Unknown package but premium rear comfort",
                }
            ],
            "additional_features": [],
        }
        validated = validate_ai_feature_selection(payload, raw)
        flattened = flatten_validated_features(validated)
        self.assertIn("Executive Rear Seat Package", flattened)

    def test_generic_marketing_phrases_are_rejected(self):
        raw = "Panoramic roof\nBurmester"
        payload = {
            "headline_features": [
                {
                    "source_feature": "Panoramic roof",
                    "display_name_bg": "Премиум изпълнение",
                    "reason": "bad",
                }
            ],
            "additional_features": [],
        }
        validated = validate_ai_feature_selection(payload, raw)
        self.assertEqual(flatten_validated_features(validated), [])

    def test_every_feature_must_be_grounded_in_source(self):
        raw = "Panoramic roof\nBurmester"
        payload = {
            "headline_features": [
                {
                    "source_feature": "Night Vision Assist",
                    "display_name_bg": "Night Vision Assist",
                    "reason": "not present",
                }
            ],
            "additional_features": [],
        }
        validated = validate_ai_feature_selection(payload, raw)
        self.assertEqual(flatten_validated_features(validated), [])

    def test_fewer_real_features_preferred_over_invented_filler(self):
        raw = "4MATIC\nPanoramic roof\nBurmester"
        payload = {
            "headline_features": [
                {
                    "source_feature": "4MATIC",
                    "display_name_bg": "4x4 задвижване",
                    "reason": "drivetrain",
                },
                {
                    "source_feature": "Panoramic roof",
                    "display_name_bg": "Панорамен покрив",
                    "reason": "roof",
                },
                {
                    "source_feature": "Burmester",
                    "display_name_bg": "Burmester озвучаване",
                    "reason": "audio",
                },
            ],
            "additional_features": [
                {
                    "source_feature": "Bogato oborudvane",
                    "display_name_bg": "Богато оборудване",
                    "reason": "forbidden filler",
                },
                {
                    "source_feature": "Excellent setup",
                    "display_name_bg": "Отлична конфигурация",
                    "reason": "forbidden filler",
                },
            ],
        }
        validated = validate_ai_feature_selection(payload, raw)
        flattened = flatten_validated_features(validated)
        self.assertEqual(len(flattened), 3)
        self.assertNotIn("Богато оборудване", flattened)
        self.assertNotIn("Отлична конфигурация", flattened)

    def test_mercedes_4matic_is_preserved(self):
        raw = "Mercedes-Benz GLE 300d 4MATIC"
        payload = {
            "headline_features": [
                {
                    "source_feature": "4MATIC",
                    "display_name_bg": "4x4 задвижване",
                    "reason": "drivetrain",
                }
            ],
            "additional_features": [],
        }
        validated = validate_ai_feature_selection(payload, raw)
        flattened = flatten_validated_features(validated)
        self.assertEqual(flattened, ["4MATIC"])

    def test_app_and_standalone_produce_identical_validation(self):
        raw = """
        Mercedes-Benz GLE 300d 4MATIC
        Panoramic roof
        Burmester
        Executive Rear Seat Package
        """

        payload = {
            "headline_features": [
                {"source_feature": "4MATIC", "display_name_bg": "4x4 задвижване", "reason": "drive"},
                {"source_feature": "Panoramic roof", "display_name_bg": "Панорамен покрив", "reason": "roof"},
            ],
            "additional_features": [
                {"source_feature": "Burmester", "display_name_bg": "Burmester озвучаване", "reason": "audio"},
                {
                    "source_feature": "Executive Rear Seat Package",
                    "display_name_bg": "Executive Rear Seat Package",
                    "reason": "unknown premium",
                },
            ],
        }

        app_validated = validate_ai_feature_selection(payload, raw)

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
                    sys.modules.pop("app.feature_selection", None)
                    with patch.object(sys, "path", filtered_sys_path):
                        module = load_module_from_path("encar_download2_feature_parity", temp_script)

                standalone_validated = module.validate_ai_feature_selection(payload, raw)
            finally:
                if original_api_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = original_api_key

        self.assertEqual(app_validated, standalone_validated)


if __name__ == "__main__":
    unittest.main()

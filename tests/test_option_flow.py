from pathlib import Path
from unittest.mock import patch

from app.generator import process_encar


DETAIL_HTML = (
    "<html><body>"
    "<script>var x=1;</script>"
    "<div>Mercedes-Benz GLE 300d 4MATIC</div>"
    "<div>360 camera</div>"
    "<div>5,473 km</div>"
    "</body></html>"
)


def test_generator_uses_clean_detail_text_only_for_ai_input():
    captured = {}

    def fake_generate(car_context):
        captured["raw_car_text"] = car_context["raw_car_text"]
        return {
            "title": "Mercedes-Benz GLE 300d 4MATIC",
            "fuel": "Дизел",
            "transmission": "Автоматик",
            "short_accent": "AIRMATIC | Burmester | 360° камера",
            "strong_highlights": ["AIRMATIC", "Burmester", "360° камера"],
            "facebook_post": "",
        }

    with patch("app.generator.download_html", return_value=DETAIL_HTML), \
         patch("app.generator.extract_price_krw", return_value=95_000_000), \
         patch("app.generator.extract_year", return_value=2023), \
         patch("app.generator.extract_mileage", return_value=54736), \
         patch("app.generator.get_eur_to_krw_rate_info", return_value=(1600.0, "2026-07-14")), \
         patch("app.generator.calculate_final_price_eur", return_value=(68500, 8000)), \
         patch("app.generator.generate_facebook_data_with_openai", side_effect=fake_generate), \
         patch("app.generator.build_facebook_post", return_value="OK"), \
         patch("app.generator.download_images", return_value=[]), \
         patch("app.generator.create_zip", return_value=None):
        result = process_encar("https://fem.encar.com/cars/detail/41237726")

    assert result["facebook_post"] == "OK"
    assert "360 camera" in captured["raw_car_text"]
    assert "var x=1" not in captured["raw_car_text"]


def test_no_option_page_or_structured_validator_in_active_flow():
    generator_source = Path("app/generator.py").read_text(encoding="utf-8")
    openai_source = Path("app/openai_service.py").read_text(encoding="utf-8")

    assert "extract_complete_option_context_from_detail_html" not in generator_source
    assert "/cars/option/" not in generator_source
    assert "validate_ai_feature_selection" not in openai_source
    assert "headline_features" not in openai_source
    assert "source_option_code" not in openai_source


def test_main_and_standalone_use_legacy_generation_path():
    script_source = Path("external-script/encar_download2.py").read_text(encoding="utf-8")
    app_source = Path("app/openai_service.py").read_text(encoding="utf-8")

    assert "from app.encar_options import" not in script_source
    assert "from app.feature_prompt import" not in script_source
    assert "from app.feature_selection import" not in script_source
    assert "build_legacy_openai_prompt" in script_source
    assert "build_legacy_openai_prompt" in app_source

from pathlib import Path
from unittest.mock import patch

from app.encar_options import extract_complete_option_context_from_detail_html
from app.generator import process_encar


DETAIL_HTML = (
    "<html><body>"
    "<script>__PRELOADED_STATE__ = {\"cars\":{\"base\":{\"vehicleId\":41232209,\"queryCarId\":41237726}}}</script>"
    "<ul><li>선루프 있음</li><li>가죽시트 있음</li></ul>"
    "</body></html>"
)


def test_option_page_failure_returns_explicit_incomplete_mode():
    with patch("app.encar_options.requests.get", side_effect=RuntimeError("network down")):
        context = extract_complete_option_context_from_detail_html(
            detail_html=DETAIL_HTML,
            detail_url="https://fem.encar.com/cars/detail/41237726",
        )

    assert context["is_incomplete"] is True
    assert context["incomplete_reason"].startswith("option_page_or_api_load_failed")
    assert len(context["applied_options"]) == 2


def test_generator_passes_full_applied_options_to_ai_and_no_generic_filler():
    fake_option_context = {
        "vehicle_id": 41232209,
        "detail_query_car_id": 41237726,
        "source_url": "https://fem.encar.com/cars/option/41232209",
        "applied_options": [
            {
                "code": "079",
                "source_name": "DISTRONIC",
                "display_name_bg": None,
                "category": "Convenience / Multimedia",
                "is_applied": True,
                "source_url": "https://fem.encar.com/cars/option/41232209",
                "source_language": "ko",
            },
            {
                "code": "500",
                "source_name": "Burmester",
                "display_name_bg": None,
                "category": "Convenience / Multimedia",
                "is_applied": True,
                "source_url": "https://fem.encar.com/cars/option/41232209",
                "source_language": "ko",
            },
        ],
        "all_option_entries": [],
        "unresolved_option_codes": [],
        "total_options_displayed": 53,
        "applied_options_count": 2,
        "main_options": ["선루프", "가죽시트"],
        "is_incomplete": False,
        "incomplete_reason": None,
        "applied_code_pools": {"standard": ["079", "500"], "choice": [], "etc": [], "tuning": []},
        "metadata": {
            "manufacturer": "Mercedes-Benz",
            "model": "GLE-Class",
            "grade": "GLE300d 4MATIC",
            "grade_detail": None,
            "drivetrain_designation": "4MATIC",
        },
    }

    captured = {}

    def fake_generate(car_context):
        captured["car_context"] = car_context
        return {
            "title": "Mercedes-Benz GLE300d 4MATIC",
            "fuel": "Дизел",
            "transmission": "Автоматик",
            "short_accent": "DISTRONIC | Burmester",
            "strong_highlights": ["DISTRONIC", "Burmester"],
            "headline_features": [],
            "additional_features": [],
        }

    with patch("app.generator.download_html", return_value=DETAIL_HTML), \
         patch("app.generator.extract_price_krw", return_value=95000000), \
         patch("app.generator.extract_year", return_value=2023), \
         patch("app.generator.extract_mileage", return_value=54736), \
         patch("app.generator.get_eur_to_krw_rate_info", return_value=(1600.0, "2026-07-14")), \
         patch("app.generator.calculate_final_price_eur", return_value=(68500, 8000)), \
         patch("app.generator.extract_complete_option_context_from_detail_html", return_value=fake_option_context), \
         patch("app.generator.generate_facebook_data_with_openai", side_effect=fake_generate), \
         patch("app.generator.build_facebook_post", return_value="OK"), \
         patch("app.generator.download_images", return_value=[]), \
         patch("app.generator.create_zip", return_value=None):
        result = process_encar("https://fem.encar.com/cars/detail/41237726")

    assert result["facebook_post"] == "OK"
    ai_source_text = captured["car_context"]["ai_source_text"]
    assert "DISTRONIC" in ai_source_text
    assert "Burmester" in ai_source_text
    assert "선루프" in captured["car_context"]["main_options_evidence_block"]
    assert "Премиум изпълнение" not in ai_source_text


def test_main_and_standalone_share_option_extractor_module():
    script_path = Path("external-script/encar_download2.py")
    source = script_path.read_text(encoding="utf-8")
    assert "from app.encar_options import" in source
    assert "extract_complete_option_context_from_detail_html" in source

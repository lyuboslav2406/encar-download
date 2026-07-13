from app.encar_options import (
    build_option_context,
    build_option_page_url,
    extract_vehicle_and_detail_ids,
)


def _sample_detail_html() -> str:
    return (
        "<html><head></head><body>"
        "<script>__PRELOADED_STATE__ = {\"cars\":{\"base\":{\"vehicleId\":41232209,\"queryCarId\":41237726}}}</script>"
        "</body></html>"
    )


def _sample_vehicle_payload() -> dict:
    return {
        "vehicleId": 41232209,
        "queryCarId": 41237726,
        "category": {
            "manufacturerEnglishName": "Mercedes-Benz",
            "modelName": "GLE-Class",
            "gradeName": "GLE300d 4MATIC",
            "gradeDetailName": None,
            "gradeEnglishName": "GLE300d 4MATIC",
        },
        "options": {
            "standard": ["001", "063", "777"],
            "choice": ["079"],
            "etc": [],
            "tuning": [],
        },
    }


def _sample_options_catalog() -> dict:
    return {
        "options": [
            {
                "optionCd": "001",
                "optionName": "ABS",
                "optionTypeCd": "02",
                "optionTitle": "ABS",
                "groupOptionName": "ABS",
                "subOptions": [
                    {
                        "optionCd": "063",
                        "optionName": "열선시트(앞좌석, 뒷좌석)",
                        "optionTypeCd": "04",
                        "optionTitle": "열선시트",
                        "groupOptionName": "열선시트",
                        "subOptions": None,
                    }
                ],
            },
            {
                "optionCd": "079",
                "optionName": "DISTRONIC",
                "optionTypeCd": "03",
                "optionTitle": "DISTRONIC",
                "groupOptionName": "DISTRONIC",
                "subOptions": None,
            },
            {
                "optionCd": "500",
                "optionName": "Unused option",
                "optionTypeCd": "03",
                "optionTitle": "Unused option",
                "groupOptionName": "Unused option",
                "subOptions": None,
            },
        ]
    }


def test_vehicle_and_query_ids_are_extracted_separately():
    ids = extract_vehicle_and_detail_ids(_sample_detail_html(), "https://fem.encar.com/cars/detail/41237726")
    assert ids["detail_query_car_id"] == 41237726
    assert ids["vehicle_id"] == 41232209


def test_option_url_uses_vehicle_id_not_query_id():
    assert build_option_page_url(41232209) == "https://fem.encar.com/cars/option/41232209"


def test_build_option_context_returns_only_applied_options_and_excludes_non_applied():
    context = build_option_context(
        vehicle_payload=_sample_vehicle_payload(),
        options_catalog=_sample_options_catalog(),
        source_url="https://fem.encar.com/cars/option/41232209",
        detail_query_car_id=41237726,
        vehicle_id=41232209,
        main_options=["선루프", "가죽시트"],
    )

    applied_codes = [item["code"] for item in context["applied_options"]]
    assert "500" not in applied_codes
    assert set(applied_codes) == {"001", "063", "079", "777"}


def test_unknown_manufacturer_specific_or_unmapped_options_are_preserved():
    context = build_option_context(
        vehicle_payload=_sample_vehicle_payload(),
        options_catalog=_sample_options_catalog(),
        source_url="https://fem.encar.com/cars/option/41232209",
        detail_query_car_id=41237726,
        vehicle_id=41232209,
        main_options=[],
    )

    unresolved = [item for item in context["applied_options"] if item["code"] == "777"]
    assert len(unresolved) == 1
    assert unresolved[0]["source_name"] == "OPTION_CODE_777"


def test_main_options_are_secondary_and_not_treated_as_complete():
    context = build_option_context(
        vehicle_payload=_sample_vehicle_payload(),
        options_catalog=_sample_options_catalog(),
        source_url="https://fem.encar.com/cars/option/41232209",
        detail_query_car_id=41237726,
        vehicle_id=41232209,
        main_options=["선루프"],
    )

    assert context["main_options"] == ["선루프"]
    assert context["applied_options_count"] == 4
    assert context["is_incomplete"] is False

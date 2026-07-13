import json
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from .config import HEADERS

VEHICLE_READSIDE_INCLUDE = "ADVERTISEMENT,CATEGORY,CONDITION,CONTACT,MANAGE,OPTIONS,PHOTOS,SPEC,PARTNERSHIP,CENTER,VIEW"

OPTION_TYPE_TO_CATEGORY = {
    "01": "Exterior / Interior",
    "02": "Safety",
    "03": "Convenience / Multimedia",
    "04": "Seat",
}


def download_json(url: str) -> dict[str, Any]:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def extract_preloaded_state(html: str) -> dict[str, Any] | None:
    match = re.search(r"__PRELOADED_STATE__\s*=\s*(\{.*?\})</script>", html, flags=re.S)
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def extract_main_options_from_detail_html(detail_html: str) -> list[str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    options: list[str] = []

    for li in soup.find_all("li"):
        text = " ".join(li.get_text(" ", strip=True).split())
        if not text:
            continue

        if text.endswith("있음"):
            core = text[:-2].strip()
            if core and core not in options:
                options.append(core)

    return options


def extract_vehicle_and_detail_ids(detail_html: str, detail_url: str = "") -> dict[str, int | None]:
    state = extract_preloaded_state(detail_html) or {}
    base = ((state.get("cars") or {}).get("base") or {})

    detail_query_car_id = base.get("queryCarId")
    vehicle_id = base.get("vehicleId")

    if not isinstance(detail_query_car_id, int):
        url_match = re.search(r"/cars/detail/(\d+)", detail_url)
        if url_match:
            detail_query_car_id = int(url_match.group(1))

    if not isinstance(vehicle_id, int):
        vehicle_id = None

    if not isinstance(detail_query_car_id, int):
        detail_query_car_id = None

    return {
        "detail_query_car_id": detail_query_car_id,
        "vehicle_id": vehicle_id,
    }


def build_option_page_url(vehicle_id: int) -> str:
    return f"https://fem.encar.com/cars/option/{vehicle_id}"


def build_vehicle_api_url(vehicle_id: int) -> str:
    return f"https://api.encar.com/v1/readside/vehicle/{vehicle_id}?include={VEHICLE_READSIDE_INCLUDE}"


def build_standard_options_api_url(vehicle_type: str = "car") -> str:
    return f"https://api.encar.com/v1/readside/vehicles/{vehicle_type}/options/standard"


def _detect_drivetrain(category: dict[str, Any]) -> str | None:
    haystack = " ".join(
        [
            str(category.get("gradeName") or ""),
            str(category.get("gradeEnglishName") or ""),
            str(category.get("gradeDetailName") or ""),
            str(category.get("gradeDetailEnglishName") or ""),
        ]
    ).strip()

    if not haystack:
        return None

    tokens = ["4MATIC", "quattro", "xDrive", "AWD", "4WD", "FWD", "RWD"]
    for token in tokens:
        if re.search(rf"\b{re.escape(token)}\b", haystack, flags=re.IGNORECASE):
            return token

    return None


def _extract_vehicle_metadata(vehicle_payload: dict[str, Any]) -> dict[str, Any]:
    category = vehicle_payload.get("category") or {}
    return {
        "manufacturer": category.get("manufacturerEnglishName") or category.get("manufacturerName"),
        "model": category.get("modelName"),
        "grade": category.get("gradeName"),
        "grade_detail": category.get("gradeDetailName") or category.get("gradeDetailEnglishName"),
        "drivetrain_designation": _detect_drivetrain(category),
    }


def _flatten_option_catalog(options_catalog: dict[str, Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []

    for option in options_catalog.get("options") or []:
        bucket = [option]
        sub_options = option.get("subOptions") or []
        if isinstance(sub_options, list):
            bucket.extend([item for item in sub_options if isinstance(item, dict)])

        for entry in bucket:
            code = str(entry.get("optionCd") or "").strip()
            if not code:
                continue

            category = OPTION_TYPE_TO_CATEGORY.get(str(entry.get("optionTypeCd") or ""), "Other")
            source_name = (
                entry.get("optionName")
                or entry.get("groupOptionName")
                or entry.get("optionTitle")
                or code
            )

            flattened.append(
                {
                    "code": code,
                    "source_name": str(source_name),
                    "category": category,
                    "option_type_cd": entry.get("optionTypeCd"),
                    "option_title": entry.get("optionTitle"),
                    "source_language": "ko",
                }
            )

    deduped: list[dict[str, Any]] = []
    seen = set()
    for entry in flattened:
        code = entry["code"]
        if code in seen:
            continue
        seen.add(code)
        deduped.append(entry)

    return deduped


def _extract_applied_codes(vehicle_payload: dict[str, Any]) -> tuple[list[str], dict[str, list[str]]]:
    options = vehicle_payload.get("options") or {}
    pools = {
        "standard": [str(code) for code in (options.get("standard") or []) if code is not None],
        "choice": [str(code) for code in (options.get("choice") or []) if code is not None],
        "etc": [str(code) for code in (options.get("etc") or []) if code is not None],
        "tuning": [str(code) for code in (options.get("tuning") or []) if code is not None],
    }

    ordered_codes: list[str] = []
    seen = set()
    for bucket_name in ("standard", "choice", "etc", "tuning"):
        for code in pools[bucket_name]:
            if code in seen:
                continue
            seen.add(code)
            ordered_codes.append(code)

    return ordered_codes, pools


def _build_option_entry(
    *,
    code: str,
    source_name: str,
    category: str,
    source_url: str,
    is_applied: bool,
) -> dict[str, Any]:
    return {
        "code": code,
        "source_name": source_name,
        "display_name_bg": None,
        "category": category,
        "is_applied": is_applied,
        "source_url": source_url,
        "source_language": "ko",
    }


def build_option_context(
    *,
    vehicle_payload: dict[str, Any],
    options_catalog: dict[str, Any],
    source_url: str,
    detail_query_car_id: int | None,
    vehicle_id: int,
    main_options: list[str] | None = None,
) -> dict[str, Any]:
    catalog_entries = _flatten_option_catalog(options_catalog)
    by_code = {entry["code"]: entry for entry in catalog_entries}

    applied_codes, applied_code_pools = _extract_applied_codes(vehicle_payload)

    applied_options: list[dict[str, Any]] = []
    unresolved_codes: list[str] = []

    for code in applied_codes:
        catalog_entry = by_code.get(code)
        if catalog_entry:
            applied_options.append(
                _build_option_entry(
                    code=code,
                    source_name=catalog_entry["source_name"],
                    category=catalog_entry["category"],
                    source_url=source_url,
                    is_applied=True,
                )
            )
            continue

        unresolved_codes.append(code)
        applied_options.append(
            _build_option_entry(
                code=code,
                source_name=f"OPTION_CODE_{code}",
                category="Other",
                source_url=source_url,
                is_applied=True,
            )
        )

    metadata = _extract_vehicle_metadata(vehicle_payload)

    return {
        "vehicle_id": vehicle_id,
        "detail_query_car_id": detail_query_car_id,
        "source_url": source_url,
        "applied_options": applied_options,
        "all_option_entries": [
            _build_option_entry(
                code=entry["code"],
                source_name=entry["source_name"],
                category=entry["category"],
                source_url=source_url,
                is_applied=entry["code"] in set(applied_codes),
            )
            for entry in catalog_entries
        ],
        "unresolved_option_codes": unresolved_codes,
        "total_options_displayed": len(catalog_entries),
        "applied_options_count": len(applied_options),
        "main_options": list(main_options or []),
        "is_incomplete": False,
        "incomplete_reason": None,
        "applied_code_pools": applied_code_pools,
        "metadata": metadata,
    }


def _fallback_context(
    *,
    detail_query_car_id: int | None,
    vehicle_id: int | None,
    source_url: str,
    main_options: list[str],
    reason: str,
) -> dict[str, Any]:
    fallback_applied = [
        {
            "code": None,
            "source_name": option,
            "display_name_bg": None,
            "category": "Other",
            "is_applied": True,
            "source_url": source_url,
            "source_language": "ko",
        }
        for option in main_options
    ]

    return {
        "vehicle_id": vehicle_id,
        "detail_query_car_id": detail_query_car_id,
        "source_url": source_url,
        "applied_options": fallback_applied,
        "all_option_entries": fallback_applied,
        "unresolved_option_codes": [],
        "total_options_displayed": len(main_options),
        "applied_options_count": len(main_options),
        "main_options": list(main_options),
        "is_incomplete": True,
        "incomplete_reason": reason,
        "applied_code_pools": {"standard": [], "choice": [], "etc": [], "tuning": []},
        "metadata": {
            "manufacturer": None,
            "model": None,
            "grade": None,
            "grade_detail": None,
            "drivetrain_designation": None,
        },
    }


def extract_complete_option_context_from_detail_html(detail_html: str, detail_url: str) -> dict[str, Any]:
    ids = extract_vehicle_and_detail_ids(detail_html, detail_url)
    detail_query_car_id = ids["detail_query_car_id"]
    vehicle_id = ids["vehicle_id"]

    main_options = extract_main_options_from_detail_html(detail_html)

    if vehicle_id is None:
        return _fallback_context(
            detail_query_car_id=detail_query_car_id,
            vehicle_id=None,
            source_url=detail_url,
            main_options=main_options,
            reason="vehicle_id_missing_in_detail_preloaded_state",
        )

    option_page_url = build_option_page_url(vehicle_id)

    try:
        option_page_html = requests.get(option_page_url, headers=HEADERS, timeout=30)
        option_page_html.raise_for_status()
        option_page_raw_html = option_page_html.text

        vehicle_payload = download_json(build_vehicle_api_url(vehicle_id))
        options_catalog = download_json(build_standard_options_api_url("car"))

        context = build_option_context(
            vehicle_payload=vehicle_payload,
            options_catalog=options_catalog,
            source_url=option_page_url,
            detail_query_car_id=detail_query_car_id,
            vehicle_id=vehicle_id,
            main_options=main_options,
        )

        detail_state = extract_preloaded_state(detail_html)
        context["debug_artifacts"] = {
            "detail_preloaded_state": detail_state,
            "option_page_html": option_page_raw_html,
        }
        return context
    except Exception as exc:
        return _fallback_context(
            detail_query_car_id=detail_query_car_id,
            vehicle_id=vehicle_id,
            source_url=option_page_url,
            main_options=main_options,
            reason=f"option_page_or_api_load_failed:{type(exc).__name__}",
        )


def build_applied_option_evidence_block(option_context: dict[str, Any], max_lines: int = 240) -> str:
    applied_options = option_context.get("applied_options") or []
    if not applied_options:
        return "(няма приложени опции)"

    lines: list[str] = []
    for item in applied_options[:max_lines]:
        source_name = str(item.get("source_name") or "").strip()
        if not source_name:
            continue

        code = item.get("code")
        category = str(item.get("category") or "Other")

        if code:
            lines.append(f"- [{category}] {source_name} (code: {code})")
        else:
            lines.append(f"- [{category}] {source_name}")

    return "\n".join(lines) if lines else "(няма приложени опции)"


def build_main_options_evidence_block(option_context: dict[str, Any]) -> str:
    main_options = option_context.get("main_options") or []
    if not main_options:
        return "(няма основни опции)"
    return "\n".join(f"- {item}" for item in main_options)

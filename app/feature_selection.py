import re
from typing import Any


FORBIDDEN_GENERIC_FEATURE_PHRASES = (
    "премиум изпълнение",
    "богато оборудване",
    "отлична конфигурация",
    "отлично оборудване",
    "луксозно изпълнение",
    "комфортен интериор",
    "подходящ избор за внос",
    "премиум автомобил",
    "високо ниво на комфорт",
    "богата конфигурация",
    "комфортен кожен салон",
)

FORBIDDEN_NON_EQUIPMENT_TERMS = (
    "encar warranty",
    "korean warranty",
    "manufacturer warranty",
    "remaining warranty",
    "extended warranty",
    "warranty",
    "гаранц",
    "безавари",
    "accident",
    "import",
    "внос",
)

UI_NOISE_TERMS = (
    "기본정보",
    "옵션정보",
    "차량상태",
    "보증현황",
    "엔카서비스",
    "신고하기",
    "프린트",
    "공유하기",
    "찜하기",
    "가격",
    "고객센터",
    "이용약관",
)

BASELINE_TERMS = (
    "leather",
    "кож",
    "heated front",
    "подгрев",
    "automatic transmission",
    "автоматик",
    "climate",
    "климат",
    "smart key",
    "스마트키",
    "navigation",
    "내비게이션",
    "parking sensor",
    "주차감지센서",
)

PANORAMIC_HINTS = (
    "panoramic",
    "panorama",
    "dual-panel",
    "wide sunroof",
    "panorama sliding",
    "파노라마",
)

SUNROOF_HINTS = (
    "sunroof",
    "moonroof",
    "선루프",
    "люк",
)

ADVANCED_LIGHTING_HINTS = (
    "multibeam",
    "matrix",
    "laser",
    "pixel",
)

PREMIUM_BRANDS = (
    "mercedes",
    "bmw",
    "audi",
    "porsche",
    "range rover",
    "land rover",
    "lexus",
    "genesis",
)

PREMIUM_MODELS = (
    "gle",
    "gls",
    "x5",
    "x6",
    "x7",
    "q7",
    "q8",
    "cayenne",
    "range rover",
)

ROOF_OPTION_CODES = {
    "010",
    "011",
    "012",
    "013",
    "014",
}

ROOF_HINTS = PANORAMIC_HINTS + SUNROOF_HINTS + (
    "roof opening",
    "sliding roof",
    "sun roof",
    "moon roof",
    "파노라마 선루프",
    "선루프",
    "люк",
)

CAMERA_360_HINTS = (
    "360",
    "around view",
    "surround view",
    "bird view",
    "aroundview",
    "surroundview",
    "околен изглед",
)

HEAD_UP_HINTS = (
    "head-up",
    "head up",
    "hud",
    "дисплей на главата",
)

TAILGATE_HINTS = (
    "power tailgate",
    "power liftgate",
    "electric tailgate",
    "electrical tailgate",
    "електрически багажник",
    "tailgate",
    "liftgate",
)

SOFT_CLOSE_HINTS = (
    "soft close",
    "ghost door closing",
    "vakuum",
    "вакуум",
)

BLIND_SPOT_HINTS = (
    "blind spot",
    "mrtva zona",
    "mъртва зона",
    "mъртва",
    "dead angle",
)

LANE_KEEP_HINTS = (
    "lane keep",
    "lane keeping",
    "lane departure",
    "lka",
    "поддържане на лентата",
)

ADAPTIVE_CRUISE_HINTS = (
    "adaptive cruise",
    "distronic",
    "cruise control",
    "adaptive",
    "круиз",
)

SEAT_MEMORY_HINTS = (
    "memory seat",
    "seat memory",
    "памет на седал",
    "memory function",
    "memory",
)

SEAT_VENTILATED_HINTS = (
    "ventilat",
    "seat cooling",
    "seat cooler",
    "вентилир",
    "охлажд",
    "обдух",
    "ventilated",
)

SEAT_DRIVER_HINTS = (
    "driver",
    "driv",
    "шофьор",
    "водач",
)

SEAT_PASSENGER_HINTS = (
    "passenger",
    "пътник",
)

SEAT_FRONT_HINTS = (
    "front",
    "предн",
)

HERO_PACKAGE_HINTS = (
    "amg line",
    "night package",
    "m sport",
    "s line",
    "sport chrono",
    "off-road package",
    "off road package",
)

HERO_DRIVE_TECH_HINTS = (
    "airmatic",
    "distronic",
    "integral active steering",
    "rear axle steering",
    "pasm",
    "pdls",
    "multibeam",
    "matrix led",
    "laser lights",
    "laser",
    "quattro",
    "4matic",
    "xdrive",
)

HERO_AUDIO_HINTS = (
    "burmester",
    "harman kardon",
    "bang & olufsen",
    "bang and olufsen",
    "bose",
)

HERO_AWARENESS_HINTS = (
    "360",
    "around view",
    "surround view",
    "head-up",
    "head up",
    "hud",
)

HERO_COMFORT_HINTS = (
    "ventilat",
    "memory seat",
    "seat memory",
    "отопля",
    "подгрев",
)

HERO_CONVENIENCE_HINTS = (
    "power tailgate",
    "power liftgate",
    "soft close",
    "ghost door closing",
    "вакуум",
)

CHASSIS_CODE_RE = re.compile(r"\b([A-Z]\d{2,4}[A-Z]?|\d{3,4}[A-Z]?)\b")
KOREAN_SCRIPT_RE = re.compile(r"[\uac00-\ud7af]+")
TITLE_MODEL_ENDINGS = {
    "4matic",
    "quattro",
    "xdrive",
    "awd",
    "tdi",
    "tfsi",
    "fsi",
    "hdi",
    "hybrid",
    "diesel",
    "petrol",
    "gasoline",
    "electric",
    "ev",
    "turbo",
}

FUEL_LABELS = {
    "diesel": "Дизел",
    "petrol": "Бензин",
    "gasoline": "Бензин",
    "benzin": "Бензин",
    "бензин": "Бензин",
    "hybrid": "Хибрид",
    "ev": "Електрически",
    "electric": "Електрически",
    "електр": "Електрически",
}

TRANSMISSION_LABELS = {
    "automatic": "Автоматик",
    "auto": "Автоматик",
    "автомат": "Автоматик",
    "manual": "Ръчна",
    "man": "Ръчна",
    "ръчна": "Ръчна",
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "или",
    "както",
    "при",
    "за",
    "с",
    "на",
    "от",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _strip_korean_script(value: str) -> str:
    return _clean_text(KOREAN_SCRIPT_RE.sub(" ", value or ""))


def _normalize_title_source(value: str) -> str:
    text = _strip_korean_script(value)
    text = re.sub(r"[()\[\]]", " ", text)
    text = re.sub(r"[-_/]+", " ", text)
    return _clean_text(text)


def _extract_model_name(model_raw: str, fallback_title: str = "") -> str:
    for candidate in (model_raw, fallback_title):
        normalized = _normalize_title_source(candidate)
        if not normalized:
            continue

        tokens = normalized.split()
        selected: list[str] = []
        for token in tokens:
            token_l = token.lower()
            if selected and (any(ch.isdigit() for ch in token_l) or token_l in TITLE_MODEL_ENDINGS):
                break
            if selected and token_l == selected[0].lower():
                continue
            selected.append(token)

        if selected:
            return _clean_text(" ".join(selected))

    return ""


def _strip_leading_title_prefix(value: str, prefix: str) -> str:
    text = _normalize_title_source(value)
    prefix = _normalize_title_source(prefix)
    if not text or not prefix:
        return text

    prefix_pattern = re.escape(prefix)
    pattern = re.compile(rf"^(?:{prefix_pattern})(?=[\s\-_]|$|[A-Za-z0-9])", re.IGNORECASE)
    previous = None
    while text and previous != text:
        previous = text
        text = _clean_text(pattern.sub("", text, count=1))
    return text


def _remove_title_token(value: str, token: str) -> str:
    text = _clean_text(_strip_korean_script(value))
    token = _clean_text(token)
    if not text or not token:
        return text
    text = re.sub(rf"\b{re.escape(token)}\b", "", text, flags=re.IGNORECASE)
    return _clean_text(text)


def _normalized_text(value: str) -> str:
    return _clean_text(value).lower()


def _contains_any(text: str, keywords) -> bool:
    return any(keyword in text for keyword in keywords)


def _presentation_bucket(source_feature: str, display_name: str, family_key: str = "") -> int:
    candidate = _normalized_text(f"{source_feature} {display_name}")

    if _contains_any(candidate, HERO_PACKAGE_HINTS):
        return 0
    if _contains_any(candidate, HERO_DRIVE_TECH_HINTS):
        return 1
    if _contains_any(candidate, HERO_AUDIO_HINTS):
        return 2
    if _contains_any(candidate, HERO_AWARENESS_HINTS):
        return 3
    if is_roof_feature(source_feature, display_name=display_name):
        return 4
    if family_key.startswith("seat_memory") or family_key.startswith("seat_ventilated"):
        return 5
    if _contains_any(candidate, HERO_CONVENIENCE_HINTS):
        return 6
    if any(term in candidate for term in ("seat", "седал", "comfort", "комфорт", "climate", "климат")):
        return 7
    return 8


def _normalize_fuel_label(value: str) -> str:
    lowered = _normalized_text(value)
    for needle, replacement in FUEL_LABELS.items():
        if needle in lowered:
            return replacement
    return _clean_text(value) or "Бензин"


def _normalize_transmission_label(value: str) -> str:
    lowered = _normalized_text(value)
    for needle, replacement in TRANSMISSION_LABELS.items():
        if needle in lowered:
            return replacement
    return _clean_text(value) or "Автоматик"


def _split_model_and_code(value: str) -> tuple[str, str]:
    normalized = _clean_text(value)
    if not normalized:
        return "", ""

    code_match = CHASSIS_CODE_RE.search(normalized)
    chassis_code = code_match.group(1) if code_match else ""
    model_name = normalized
    if chassis_code:
        model_name = _clean_text(model_name.replace(chassis_code, ""))
    return model_name, chassis_code


def _strip_leading_model_prefix(value: str, model_name: str) -> str:
    normalized_value = _clean_text(value)
    normalized_model = _clean_text(model_name)
    if not normalized_value or not normalized_model:
        return normalized_value

    pattern = rf"^{re.escape(normalized_model)}(?=(\s|\d|$)|[\-_/])"
    stripped = re.sub(pattern, "", normalized_value, flags=re.IGNORECASE).strip()
    if stripped and stripped != normalized_value:
        return stripped

    return normalized_value


def format_bulgarian_title(car_context: dict[str, Any] | None, ai_title: str | None = None) -> str:
    context = car_context or {}
    option_context = context.get("option_context") if isinstance(context, dict) else None
    metadata = {}
    if isinstance(option_context, dict):
        metadata = option_context.get("metadata") or {}

    manufacturer = _clean_text(str(metadata.get("manufacturer") or context.get("manufacturer") or ""))
    model_raw = _clean_text(str(metadata.get("model") or context.get("model") or ""))
    grade_raw = _clean_text(str(metadata.get("grade") or context.get("grade") or ""))
    grade_detail = _clean_text(str(metadata.get("grade_detail") or context.get("grade_detail") or ""))
    fallback_title = _clean_text(str(ai_title or ""))

    chassis_code = ""
    for candidate in (model_raw, grade_raw, grade_detail, fallback_title):
        normalized_candidate = _strip_korean_script(candidate)
        code_match = CHASSIS_CODE_RE.search(normalized_candidate)
        if code_match:
            chassis_code = code_match.group(1)
            break

    model_name = _extract_model_name(model_raw, fallback_title or grade_raw or grade_detail)
    if not model_name:
        model_name = _extract_model_name(fallback_title, grade_raw or model_raw)

    title_parts = []
    if manufacturer:
        title_parts.append(manufacturer)
    if model_name:
        title_parts.append(model_name)

    grade_source = grade_raw or grade_detail or fallback_title
    if grade_source:
        grade_text = _strip_leading_title_prefix(grade_source, model_name)
        grade_text = _strip_leading_title_prefix(grade_text, manufacturer)
        grade_text = re.sub(r"\b(?:19|20)\d{2}\b", "", grade_text)
        grade_text = _normalize_title_source(grade_text)
        grade_text = _strip_leading_title_prefix(grade_text, model_name)
        grade_text = _remove_title_token(grade_text, chassis_code)
        if grade_text and grade_text not in title_parts:
            title_parts.append(grade_text)

    title = _clean_text(" ".join(title_parts))

    if chassis_code:
        title = _remove_title_token(title, chassis_code)
        title = _clean_text(f"{title} ({chassis_code})")

    if not title:
        title = fallback_title

    if title:
        title = _clean_text(_strip_korean_script(re.sub(r"\b(?:19|20)\d{2}\b", "", title)))
        title = _clean_text(title)

    return title or "Автомобил от Южна Корея"


def build_bulgarian_vehicle_presentation(car_context: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    title = format_bulgarian_title(car_context, data.get("title"))
    fuel = _normalize_fuel_label(data.get("fuel") or "")
    transmission = _normalize_transmission_label(data.get("transmission") or "")

    data["title"] = title
    data["fuel"] = fuel
    data["transmission"] = transmission
    return data


def _feature_seat_side(candidate: str) -> str:
    has_driver = _contains_any(candidate, SEAT_DRIVER_HINTS)
    has_passenger = _contains_any(candidate, SEAT_PASSENGER_HINTS)
    if has_driver and has_passenger:
        return "front"
    if _contains_any(candidate, SEAT_DRIVER_HINTS):
        return "driver"
    if _contains_any(candidate, SEAT_PASSENGER_HINTS):
        return "passenger"
    if _contains_any(candidate, SEAT_FRONT_HINTS):
        return "front"
    return ""


def _feature_display_family(source_feature: str, display_name: str) -> tuple[str, str]:
    candidate = _normalized_text(f"{source_feature} {display_name}")

    if _contains_any(candidate, CAMERA_360_HINTS):
        return "camera_360", "360° камера"
    if _contains_any(candidate, HEAD_UP_HINTS):
        return "head_up", "Head-up дисплей"
    if _contains_any(candidate, TAILGATE_HINTS):
        return "tailgate", "Електрически багажник"
    if _contains_any(candidate, SOFT_CLOSE_HINTS):
        return "soft_close", "Вакуум на вратите"
    if _contains_any(candidate, BLIND_SPOT_HINTS):
        return "blind_spot", "Асистент за мъртва зона"
    if _contains_any(candidate, LANE_KEEP_HINTS):
        return "lane_keep", "Асистент за поддържане на лентата"
    if _contains_any(candidate, ADAPTIVE_CRUISE_HINTS):
        return "adaptive_cruise", "Адаптивен круиз контрол"
    if _contains_any(candidate, SEAT_MEMORY_HINTS) and (
        _contains_any(candidate, SEAT_DRIVER_HINTS + SEAT_PASSENGER_HINTS + SEAT_FRONT_HINTS)
        or "seat" in candidate
        or "седал" in candidate
    ):
        side = _feature_seat_side(candidate)
        if side:
            return f"seat_memory_{side}", {
                "driver": "Памет на шофьорската седалка",
                "passenger": "Памет на пътническата седалка",
                "front": "Памет на предните седалки",
            }[side]
        return "seat_memory_front", "Памет на предните седалки"
    if _contains_any(candidate, SEAT_VENTILATED_HINTS) and (
        _contains_any(candidate, SEAT_DRIVER_HINTS + SEAT_PASSENGER_HINTS + SEAT_FRONT_HINTS)
        or "seat" in candidate
        or "седал" in candidate
    ):
        side = _feature_seat_side(candidate)
        if side:
            return f"seat_ventilated_{side}", {
                "driver": "Вентилирана шофьорска седалка",
                "passenger": "Вентилирана пътническа седалка",
                "front": "Вентилирани предни седалки",
            }[side]
        return "seat_ventilated_front", "Вентилирани предни седалки"

    return "", _clean_text(display_name)


def contains_forbidden_marketing_term(value: str) -> bool:
    lowered = _normalized_text(value)
    return _contains_any(lowered, FORBIDDEN_NON_EQUIPMENT_TERMS)


def _clean_code(value: Any) -> str:
    if value is None:
        return ""
    return _clean_text(str(value))


def _text_contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = _normalized_text(text)
    return any(keyword in lowered for keyword in keywords)


def _is_premium_vehicle(metadata: dict[str, Any] | None) -> bool:
    if not isinstance(metadata, dict):
        return False

    haystack = _normalized_text(
        " ".join(
            [
                str(metadata.get("manufacturer") or ""),
                str(metadata.get("model") or ""),
                str(metadata.get("grade") or ""),
                str(metadata.get("grade_detail") or ""),
            ]
        )
    )

    if any(brand in haystack for brand in PREMIUM_BRANDS):
        return True
    return any(model in haystack for model in PREMIUM_MODELS)


def _build_structured_source_index(option_context: dict[str, Any] | None) -> dict[str, Any]:
    index = {
        "applied_codes": set(),
        "applied_names": [],
        "all_names": [],
        "by_code": {},
    }

    if not isinstance(option_context, dict):
        return index

    for item in option_context.get("applied_options") or []:
        if not isinstance(item, dict):
            continue

        code = _clean_code(item.get("code"))
        source_name = _clean_text(str(item.get("source_name") or ""))
        if code:
            index["applied_codes"].add(code)
            index["by_code"][code] = item
        if source_name:
            index["applied_names"].append(source_name)
            index["all_names"].append(source_name)

    for item in option_context.get("all_option_entries") or []:
        if not isinstance(item, dict):
            continue

        source_name = _clean_text(str(item.get("source_name") or ""))
        if source_name:
            index["all_names"].append(source_name)

    return index


def is_roof_feature(source_feature: str, source_option_code: str = "", display_name: str = "") -> bool:
    candidate = _normalized_text(f"{source_feature} {display_name}")
    if source_option_code and str(source_option_code).strip() in ROOF_OPTION_CODES:
        return True
    return _contains_any(candidate, ROOF_HINTS)


def extract_source_option_lines(raw_text: str, max_lines: int = 220) -> list[str]:
    lines = []
    seen = set()

    for raw_line in (raw_text or "").splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        lowered = _normalized_text(line)
        if len(line) < 2 or len(line) > 120:
            continue
        if lowered in seen:
            continue
        if any(term in lowered for term in UI_NOISE_TERMS):
            continue
        if re.fullmatch(r"[\d,./\-: ]+", line):
            continue

        seen.add(lowered)
        lines.append(line)

        if len(lines) >= max_lines:
            break

    return lines


def build_option_evidence_block(raw_text: str, max_lines: int = 220) -> str:
    lines = extract_source_option_lines(raw_text, max_lines=max_lines)
    if not lines:
        return "(няма извлечени редове)"
    return "\n".join(f"- {line}" for line in lines)


def _brand_drivetrain_from_source(source_feature: str, raw_text: str) -> str | None:
    text = _normalized_text(f"{source_feature} {raw_text}")
    if "4matic" in text:
        return "4MATIC"
    if "quattro" in text:
        return "quattro"
    if "xdrive" in text:
        return "xDrive"
    return None


def _resolve_roof_display(
    display_name: str,
    source_feature: str,
    source_option_code: str,
    source_index: dict[str, Any],
    main_options: list[str] | None,
) -> tuple[str, str]:
    display = _clean_text(display_name)
    source = _normalized_text(source_feature)
    display_l = _normalized_text(display)
    main_blob = " ".join(main_options or [])

    evidence_parts = [source_feature, display_name, main_blob]
    if source_option_code and source_option_code in source_index.get("by_code", {}):
        entry = source_index["by_code"][source_option_code]
        evidence_parts.append(str(entry.get("source_name") or ""))
        evidence_parts.append(str(entry.get("category") or ""))

    evidence = _normalized_text(" ".join(evidence_parts))

    if "слънчев покрив" in display_l:
        display = "Електрически люк"
        display_l = _normalized_text(display)

    panoramic_hit = _text_contains_any(evidence, PANORAMIC_HINTS)

    if panoramic_hit:
        return "Панорамен покрив", "panoramic_hint_in_structured_or_text_source"

    sunroof_hit = _text_contains_any(f"{source} {display_l} {evidence}", SUNROOF_HINTS)

    if sunroof_hit:
        return "Електрически люк", "sunroof_hint_without_panoramic_evidence"

    return display, "non_roof_feature"


def normalize_feature(value: str) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = _clean_text(value)
    lowered = _normalized_text(normalized)
    if not lowered:
        return None

    if lowered in FORBIDDEN_GENERIC_FEATURE_PHRASES:
        return None
    if contains_forbidden_marketing_term(lowered):
        return None

    if "слънчев покрив" in lowered:
        return "Електрически люк"

    return normalized


def _feature_tokens(value: str) -> set[str]:
    tokens = {
        token
        for token in re.findall(r"[a-zа-я0-9]+", _normalized_text(value), flags=re.IGNORECASE)
        if len(token) >= 3 and token not in STOPWORDS
    }
    return tokens


def is_traceable_to_source(
    source_feature: str,
    raw_text: str,
    source_lines: list[str] | None = None,
    source_option_code: str = "",
    source_index: dict[str, Any] | None = None,
) -> bool:
    index = source_index or {}
    if source_option_code and source_option_code in (index.get("applied_codes") or set()):
        return True

    source_norm = _normalized_text(source_feature)
    if not source_norm:
        return False

    for entry_name in index.get("applied_names") or []:
        entry_norm = _normalized_text(entry_name)
        if source_norm == entry_norm or source_norm in entry_norm or entry_norm in source_norm:
            return True

        source_tokens = _feature_tokens(source_feature)
        entry_tokens = _feature_tokens(entry_name)
        if source_tokens and entry_tokens:
            overlap = len(source_tokens & entry_tokens) / max(len(source_tokens), 1)
            if overlap >= 0.6:
                return True

    corpus = _normalized_text(raw_text)
    if source_norm in corpus:
        return True

    lines = source_lines or extract_source_option_lines(raw_text)
    source_tokens = _feature_tokens(source_feature)
    if not source_tokens:
        return False

    for line in lines:
        line_tokens = _feature_tokens(line)
        if not line_tokens:
            continue
        overlap = len(source_tokens & line_tokens) / max(len(source_tokens), 1)
        if overlap >= 0.6:
            return True

    return False


def _is_baseline_feature(source_feature: str, display_name: str) -> bool:
    text = _normalized_text(f"{source_feature} {display_name}")
    return any(term in text for term in BASELINE_TERMS)


def _feature_capability_key(display_name: str, source_feature: str) -> str:
    candidate = _normalized_text(f"{display_name} {source_feature}")
    candidate = re.sub(r"\s+", " ", candidate).strip()

    if any(term in candidate for term in ("360", "around view", "surround", "어라운드", "aroundview")):
        return "camera_360"
    if any(term in candidate for term in SEAT_MEMORY_HINTS):
        side = _feature_seat_side(candidate)
        return f"seat_memory_{side or 'front'}"
    if any(term in candidate for term in SEAT_VENTILATED_HINTS):
        side = _feature_seat_side(candidate)
        return f"seat_ventilated_{side or 'front'}"
    if any(
        term in candidate
        for term in (
            "rear camera",
            "back camera",
            "camera rear",
            "задна камера",
            "камера заден",
            "камера зад",
            "камера заден ход",
            "후방 카메라",
        )
    ):
        return "camera_rear"
    if any(term in candidate for term in ("multibeam", "matrix", "laser", "pixel")):
        return "lighting_advanced"
    if "led" in candidate and any(term in candidate for term in ("head", "headlight", "headlights", "lamp", "фар", "светл")):
        return "lighting_basic_led"
    if any(term in candidate for term in ("ventilat", "통풍", "вентили", "вентилиран")):
        return "seat_ventilated"
    if any(term in candidate for term in ("heated", "열선", "отопля", "подгрев", "отопляем")):
        return "seat_heated"
    if any(term in candidate for term in ("distronic", "adaptive cruise", "adaptive", "어댑티브", "круиз")):
        return "adaptive_cruise"
    if any(term in candidate for term in ("navigation", "nav", "내비", "навига")):
        return "navigation"
    if any(term in candidate for term in ("smart key", "smartkey", "스마트키", "смарт")):
        return "smart_key"

    if "4matic" in candidate:
        return "4matic"
    if "quattro" in candidate:
        return "quattro"
    if "xdrive" in candidate:
        return "xdrive"
    return candidate


def normalize_display_name(
    display_name: str,
    source_feature: str,
    raw_text: str,
    source_option_code: str = "",
    source_index: dict[str, Any] | None = None,
    main_options: list[str] | None = None,
) -> tuple[str | None, str]:
    display = normalize_feature(display_name)
    if not display:
        return None, "invalid_or_forbidden_display_name"

    if is_roof_feature(source_feature, source_option_code, display):
        display, roof_reason = _resolve_roof_display(
            display,
            source_feature,
            source_option_code,
            source_index or {},
            main_options,
        )
    else:
        roof_reason = "not_roof_feature"

    family_key, canonical_display = _feature_display_family(source_feature, display)
    if family_key:
        display = canonical_display

    branded = _brand_drivetrain_from_source(source_feature, raw_text)
    if branded and any(token in _normalized_text(display) for token in ("4x4", "awd", "4wd")):
        display = branded

    if branded and branded.lower() in _normalized_text(source_feature):
        if any(token in _normalized_text(display) for token in ("задвижване", "driv", "awd", "4wd")):
            display = branded

    display = _clean_text(display)
    if not display:
        return None, "empty_display_after_normalization"

    lowered = _normalized_text(display)
    if lowered in FORBIDDEN_GENERIC_FEATURE_PHRASES:
        return None, "forbidden_generic_phrase"
    if contains_forbidden_marketing_term(lowered):
        return None, "forbidden_non_equipment_term"

    return display, roof_reason


def _capability_is_weaker_than_existing(capability_key: str, accepted_capabilities: set[str]) -> tuple[bool, str]:
    if capability_key == "camera_rear" and "camera_360" in accepted_capabilities:
        return True, "duplicate_capability_rear_camera_vs_360"
    if capability_key == "lighting_basic_led" and "lighting_advanced" in accepted_capabilities:
        return True, "duplicate_capability_basic_led_vs_advanced_lighting"
    if capability_key == "seat_heated" and "seat_ventilated" in accepted_capabilities:
        return True, "weak_baseline_displaced_by_stronger_feature"
    if capability_key == "navigation" and "camera_360" in accepted_capabilities:
        return True, "weak_baseline_displaced_by_stronger_feature"
    if capability_key == "smart_key" and len(accepted_capabilities) >= 3:
        return True, "weak_baseline_displaced_by_stronger_feature"
    return False, ""


def validate_ai_feature_selection(
    payload: dict[str, Any],
    raw_text: str,
    max_headline: int = 3,
    max_additional: int = 6,
    option_context: dict[str, Any] | None = None,
    vehicle_metadata: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, str]]]:
    source_lines = extract_source_option_lines(raw_text)
    source_index = _build_structured_source_index(option_context)
    main_options = []
    if isinstance(option_context, dict):
        main_options = list(option_context.get("main_options") or [])

    accepted = {"headline_features": [], "additional_features": []}
    rejected_features: list[dict[str, str]] = []
    roof_diagnostics: list[dict[str, str]] = []
    validation_debug_trace: list[dict[str, Any]] = []
    capability_seen: set[str] = set()

    premium_vehicle = _is_premium_vehicle(vehicle_metadata)

    for section, limit in (("headline_features", max_headline), ("additional_features", max_additional)):
        items = payload.get(section)
        if not isinstance(items, list):
            continue

        for item in items:
            if len(accepted[section]) >= limit:
                break
            if not isinstance(item, dict):
                continue

            source_feature = _clean_text(str(item.get("source_feature") or ""))
            display_name_bg = _clean_text(str(item.get("display_name_bg") or ""))
            source_option_code = _clean_code(item.get("source_option_code"))
            reason = _clean_text(str(item.get("reason") or ""))
            confidence = _clean_text(str(item.get("confidence") or "high")) or "high"
            current_is_roof_feature = is_roof_feature(source_feature, source_option_code, display_name_bg)

            base_rejected = {
                "section": section,
                "source_feature": source_feature,
                "source_option_code": source_option_code,
                "display_name_bg": display_name_bg,
            }
            trace_entry = {
                "section": section,
                "source_feature": source_feature,
                "source_option_code": source_option_code,
                "original_display_name": display_name_bg,
                "is_roof_feature": current_is_roof_feature,
                "roof_evidence": "",
                "resolved_display_name": "",
                "capability_key": "",
                "accepted": False,
                "rejection_reason": "",
            }

            if not source_feature or not display_name_bg:
                rejection_reason = "missing_required_fields"
                rejected_features.append({**base_rejected, "reason": rejection_reason})
                trace_entry["rejection_reason"] = rejection_reason
                validation_debug_trace.append(trace_entry)
                continue
            if not is_traceable_to_source(
                source_feature,
                raw_text,
                source_lines=source_lines,
                source_option_code=source_option_code,
                source_index=source_index,
            ):
                rejection_reason = "not_grounded"
                rejected_features.append({**base_rejected, "reason": rejection_reason})
                trace_entry["rejection_reason"] = rejection_reason
                validation_debug_trace.append(trace_entry)
                continue

            normalized_display, roof_reason = normalize_display_name(
                display_name_bg,
                source_feature,
                raw_text,
                source_option_code=source_option_code,
                source_index=source_index,
                main_options=main_options,
            )
            trace_entry["roof_evidence"] = roof_reason
            trace_entry["resolved_display_name"] = normalized_display or ""
            if "roof" in _normalized_text(f"{source_feature} {display_name_bg}") or "sunroof" in _normalized_text(
                f"{source_feature} {display_name_bg}"
            ) or "선루프" in _normalized_text(f"{source_feature} {display_name_bg}"):
                roof_diagnostics.append(
                    {
                        "source_feature": source_feature,
                        "source_option_code": source_option_code,
                        "display_name_bg": display_name_bg,
                        "resolved_display_name": normalized_display or "",
                        "roof_reason": roof_reason,
                    }
                )

            if not normalized_display:
                rejection_reason = roof_reason or "normalization_failed"
                rejected_features.append({**base_rejected, "reason": rejection_reason})
                trace_entry["rejection_reason"] = rejection_reason
                validation_debug_trace.append(trace_entry)
                continue

            capability_key = _feature_capability_key(normalized_display, source_feature)
            trace_entry["capability_key"] = capability_key
            if not capability_key:
                rejection_reason = "empty_capability_key"
                rejected_features.append({**base_rejected, "reason": rejection_reason})
                trace_entry["rejection_reason"] = rejection_reason
                validation_debug_trace.append(trace_entry)
                continue
            if capability_key in capability_seen:
                rejection_reason = "duplicate_capability"
                rejected_features.append({**base_rejected, "reason": rejection_reason})
                trace_entry["rejection_reason"] = rejection_reason
                validation_debug_trace.append(trace_entry)
                continue

            is_baseline = _is_baseline_feature(source_feature, normalized_display)
            weaker, weaker_reason = _capability_is_weaker_than_existing(capability_key, capability_seen)
            if weaker:
                rejected_features.append({**base_rejected, "reason": weaker_reason})
                trace_entry["rejection_reason"] = weaker_reason
                validation_debug_trace.append(trace_entry)
                continue

            accepted_item = {
                "source_feature": source_feature,
                "source_option_code": source_option_code,
                "display_name_bg": normalized_display,
                "display_family_key": _feature_display_family(source_feature, normalized_display)[0],
                "reason": reason,
                "confidence": confidence,
            }

            if is_baseline and premium_vehicle:
                if len(accepted["headline_features"]) + len(accepted["additional_features"]) >= 3:
                    rejection_reason = "weak_baseline_displaced_by_stronger_feature"
                    rejected_features.append(
                        {
                            **base_rejected,
                            "reason": rejection_reason,
                        }
                    )
                    trace_entry["rejection_reason"] = rejection_reason
                    validation_debug_trace.append(trace_entry)
                    continue

            accepted[section].append(accepted_item)
            capability_seen.add(capability_key)
            trace_entry["accepted"] = True
            validation_debug_trace.append(trace_entry)

    accepted["rejected_features"] = rejected_features
    accepted["roof_classification_diagnostics"] = roof_diagnostics
    accepted["validation_debug_trace"] = validation_debug_trace

    return accepted


def flatten_validated_features(validated: dict[str, list[dict[str, str]]]) -> list[str]:
    prioritized: list[tuple[int, int, str]] = []
    grouped: dict[str, list[dict[str, str]]] = {}
    sequence = 0
    for section in ("headline_features", "additional_features"):
        for item in validated.get(section, []):
            family_key = _clean_text(str(item.get("display_family_key") or ""))
            if family_key.startswith("seat_memory"):
                grouped.setdefault("seat_memory", []).append(item)
                sequence += 1
                continue
            if family_key.startswith("seat_ventilated"):
                grouped.setdefault("seat_ventilated", []).append(item)
                sequence += 1
                continue

            display_name = item.get("display_name_bg")
            if display_name:
                bucket = _presentation_bucket(
                    str(item.get("source_feature") or ""),
                    display_name,
                    family_key,
                )
                prioritized.append((bucket, sequence, display_name))
            sequence += 1

    for family_key in ("seat_memory", "seat_ventilated"):
        items = grouped.get(family_key) or []
        if not items:
            continue

        sides = []
        for item in items:
            raw_label = _normalized_text(f"{item.get('source_feature') or ''} {item.get('display_name_bg') or ''}")
            sides.append(_feature_seat_side(raw_label))

        sides_set = {side for side in sides if side}
        if family_key == "seat_memory":
            if "front" in sides_set or ("driver" in sides_set and "passenger" in sides_set):
                label = "Памет на предните седалки"
            elif "driver" in sides_set:
                label = "Памет на шофьорската седалка"
            elif "passenger" in sides_set:
                label = "Памет на пътническата седалка"
            else:
                label = "Памет на предните седалки"
        else:
            if "front" in sides_set or ("driver" in sides_set and "passenger" in sides_set):
                label = "Вентилирани предни седалки"
            elif "driver" in sides_set:
                label = "Вентилирана шофьорска седалка"
            elif "passenger" in sides_set:
                label = "Вентилирана пътническа седалка"
            else:
                label = "Вентилирани предни седалки"

        bucket = 5
        prioritized.append((bucket, sequence, label))
        sequence += 1

    result = []
    for _, _, display_name in sorted(prioritized, key=lambda entry: (entry[0], entry[1], _normalized_text(entry[2]))):
        if display_name and display_name not in result:
            result.append(display_name)
    return result


def build_short_accent(highlights: list[str]) -> str:
    top_three = [item for item in (highlights or [])[:3] if item]
    return " | ".join(top_three)


def build_short_accent_from_validated(validated: dict[str, list[dict[str, str]]]) -> str:
    prioritized = flatten_validated_features(validated)
    return build_short_accent(prioritized)


def remove_accent_duplicates(highlights: list[str], short_accent: str) -> list[str]:
    accent_items = {
        _normalized_text(part)
        for part in short_accent.split("|")
        if _normalized_text(part)
    }

    result = []
    for item in highlights:
        if _normalized_text(item) in accent_items:
            continue
        if item not in result:
            result.append(item)

    return result

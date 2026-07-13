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
)

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


def _normalized_text(value: str) -> str:
    return _clean_text(value).lower()


def _contains_any(text: str, keywords) -> bool:
    return any(keyword in text for keyword in keywords)


def contains_forbidden_marketing_term(value: str) -> bool:
    lowered = _normalized_text(value)
    return _contains_any(lowered, FORBIDDEN_NON_EQUIPMENT_TERMS)


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


def _normalize_sunroof_display(display_name: str, source_feature: str) -> str:
    display = _clean_text(display_name)
    source = _normalized_text(source_feature)
    display_l = _normalized_text(display)

    if "слънчев покрив" in display_l:
        display = "Електрически люк"
        display_l = _normalized_text(display)

    panoramic_hit = any(
        key in source for key in ("panoramic", "panorama", "панорам")
    ) or any(
        key in display_l for key in ("panoramic", "panorama", "панорам")
    )

    if panoramic_hit:
        return "Панорамен покрив"

    sunroof_hit = any(
        key in source for key in ("sunroof", "moonroof", "люк")
    ) or any(
        key in display_l for key in ("sunroof", "moonroof", "люк")
    )

    if sunroof_hit:
        return "Електрически люк"

    return display


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


def is_traceable_to_source(source_feature: str, raw_text: str, source_lines: list[str] | None = None) -> bool:
    source_norm = _normalized_text(source_feature)
    if not source_norm:
        return False

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
    candidate = _normalized_text(display_name or source_feature)
    candidate = re.sub(r"[^a-zа-я0-9]+", " ", candidate).strip()
    if "4matic" in candidate:
        return "4matic"
    if "quattro" in candidate:
        return "quattro"
    if "xdrive" in candidate:
        return "xdrive"
    return candidate


def normalize_display_name(display_name: str, source_feature: str, raw_text: str) -> str | None:
    display = normalize_feature(display_name)
    if not display:
        return None

    display = _normalize_sunroof_display(display, source_feature)

    branded = _brand_drivetrain_from_source(source_feature, raw_text)
    if branded and any(token in _normalized_text(display) for token in ("4x4", "awd", "4wd")):
        display = branded

    if branded and branded.lower() in _normalized_text(source_feature):
        if any(token in _normalized_text(display) for token in ("задвижване", "driv", "awd", "4wd")):
            display = branded

    display = _clean_text(display)
    if not display:
        return None

    lowered = _normalized_text(display)
    if lowered in FORBIDDEN_GENERIC_FEATURE_PHRASES:
        return None
    if contains_forbidden_marketing_term(lowered):
        return None

    return display


def validate_ai_feature_selection(
    payload: dict[str, Any],
    raw_text: str,
    max_headline: int = 3,
    max_additional: int = 6,
) -> dict[str, list[dict[str, str]]]:
    source_lines = extract_source_option_lines(raw_text)
    accepted = {"headline_features": [], "additional_features": []}
    capability_seen = set()

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
            reason = _clean_text(str(item.get("reason") or ""))

            if not source_feature or not display_name_bg:
                continue
            if not is_traceable_to_source(source_feature, raw_text, source_lines=source_lines):
                continue

            normalized_display = normalize_display_name(display_name_bg, source_feature, raw_text)
            if not normalized_display:
                continue

            capability_key = _feature_capability_key(normalized_display, source_feature)
            if not capability_key or capability_key in capability_seen:
                continue

            accepted_item = {
                "source_feature": source_feature,
                "display_name_bg": normalized_display,
                "reason": reason,
            }

            if section == "additional_features" and _is_baseline_feature(source_feature, normalized_display):
                # Keep baseline features only if higher-value items are not available.
                if len(accepted["headline_features"]) + len(accepted["additional_features"]) >= 3:
                    continue

            accepted[section].append(accepted_item)
            capability_seen.add(capability_key)

    return accepted


def flatten_validated_features(validated: dict[str, list[dict[str, str]]]) -> list[str]:
    result = []
    for section in ("headline_features", "additional_features"):
        for item in validated.get(section, []):
            display_name = item.get("display_name_bg")
            if display_name and display_name not in result:
                result.append(display_name)
    return result


def build_short_accent(highlights: list[str]) -> str:
    top_three = [item for item in (highlights or [])[:3] if item]
    return " | ".join(top_three)


def build_short_accent_from_validated(validated: dict[str, list[dict[str, str]]]) -> str:
    headline = [item.get("display_name_bg", "") for item in validated.get("headline_features", [])]
    return build_short_accent([item for item in headline if item])


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

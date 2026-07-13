import os
import re
import json
import math
import sys
import shutil
import requests
from pathlib import Path
from typing import Any
from bs4 import BeautifulSoup
from openai import OpenAI

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from app.pricing import (
        FRANKFURTER_SOURCE,
        ExchangeRateError,
        get_eur_to_krw_rate_info,
        krw_to_eur_with_rate,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "app.pricing"}:
        raise

    # This utility is intentionally distributed as a standalone local script.
    # When the repository package is available, we use shared production pricing.
    FRANKFURTER_SOURCE = "Frankfurter"
    FRANKFURTER_EUR_KRW_URL = "https://api.frankfurter.dev/v2/rate/EUR/KRW"
    MIN_PLAUSIBLE_KRW_PER_EUR = 500
    MAX_PLAUSIBLE_KRW_PER_EUR = 5000

    class ExchangeRateError(ValueError):
        pass

    def _validate_krw_per_eur(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ExchangeRateError(f"Invalid EUR->KRW rate type: {type(value).__name__}")

        krw_per_eur = float(value)

        if not math.isfinite(krw_per_eur):
            raise ExchangeRateError(f"Invalid EUR->KRW rate value: {krw_per_eur}")

        if krw_per_eur <= 0:
            raise ExchangeRateError(f"Invalid EUR->KRW rate value: {krw_per_eur}")

        if not (MIN_PLAUSIBLE_KRW_PER_EUR <= krw_per_eur <= MAX_PLAUSIBLE_KRW_PER_EUR):
            raise ExchangeRateError(
                f"Implausible EUR->KRW rate: {krw_per_eur}. "
                f"Expected {MIN_PLAUSIBLE_KRW_PER_EUR}-{MAX_PLAUSIBLE_KRW_PER_EUR} KRW per EUR."
            )

        return krw_per_eur

    def _parse_eur_to_krw_response(data: Any) -> tuple[float, str | None]:
        if not isinstance(data, dict):
            raise ExchangeRateError(f"Unexpected exchange-rate response type: {type(data).__name__}")

        required_fields = ["date", "base", "quote", "rate"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ExchangeRateError(f"Missing exchange-rate fields {missing_fields} in response: {data}")

        base = data["base"]
        quote = data["quote"]
        if base != "EUR" or quote != "KRW":
            raise ExchangeRateError(f"Unexpected exchange-rate pair: {base}/{quote}")

        date = data["date"]
        if not isinstance(date, str):
            raise ExchangeRateError(f"Invalid exchange-rate date type: {type(date).__name__}")

        krw_per_eur = _validate_krw_per_eur(data["rate"])

        return krw_per_eur, date

    def get_eur_to_krw_rate_info() -> tuple[float, str | None]:
        response = requests.get(FRANKFURTER_EUR_KRW_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        return _parse_eur_to_krw_response(data)

    def krw_to_eur_with_rate(krw_price: int | float, krw_per_eur: float) -> float:
        validated_krw_per_eur = _validate_krw_per_eur(krw_per_eur)
        return float(krw_price) / validated_krw_per_eur

from app.encar_options import (
    build_applied_option_evidence_block,
    build_main_options_evidence_block,
    extract_complete_option_context_from_detail_html,
)

try:
    from app.feature_selection import (
        build_option_evidence_block,
        build_short_accent,
        build_short_accent_from_validated,
        flatten_validated_features,
        normalize_feature,
        remove_accent_duplicates,
        validate_ai_feature_selection,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "app.feature_selection"}:
        raise

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

    def _contains_any(text: str, keywords):
        return any(keyword in text for keyword in keywords)

    def _contains_forbidden_term(value: str) -> bool:
        lowered = _normalized_text(value)
        return _contains_any(lowered, FORBIDDEN_NON_EQUIPMENT_TERMS)

    def extract_source_option_lines(raw_text: str, max_lines: int = 220):
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

    def build_option_evidence_block(raw_text: str, max_lines: int = 220):
        lines = extract_source_option_lines(raw_text, max_lines=max_lines)
        if not lines:
            return "(няма извлечени редове)"
        return "\n".join(f"- {line}" for line in lines)

    def _brand_drivetrain_from_source(source_feature: str, raw_text: str):
        text = _normalized_text(f"{source_feature} {raw_text}")
        if "4matic" in text:
            return "4MATIC"
        if "quattro" in text:
            return "quattro"
        if "xdrive" in text:
            return "xDrive"
        return None

    def _normalize_sunroof_display(display_name: str, source_feature: str):
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

    def normalize_feature(value: str):
        if not isinstance(value, str):
            return None

        lowered = _normalized_text(value)
        if not lowered:
            return None
        if lowered in FORBIDDEN_GENERIC_FEATURE_PHRASES:
            return None
        if _contains_forbidden_term(lowered):
            return None

        if "слънчев покрив" in lowered:
            return "Електрически люк"

        return _clean_text(value)

    def _feature_tokens(value: str):
        tokens = {
            token
            for token in re.findall(r"[a-zа-я0-9]+", _normalized_text(value), flags=re.IGNORECASE)
            if len(token) >= 3 and token not in STOPWORDS
        }
        return tokens

    def is_traceable_to_source(source_feature: str, raw_text: str, source_lines=None):
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

    def _is_baseline_feature(source_feature: str, display_name: str):
        text = _normalized_text(f"{source_feature} {display_name}")
        return any(term in text for term in BASELINE_TERMS)

    def _feature_capability_key(display_name: str, source_feature: str):
        candidate = _normalized_text(display_name or source_feature)
        candidate = re.sub(r"[^a-zа-я0-9]+", " ", candidate).strip()
        if "4matic" in candidate:
            return "4matic"
        if "quattro" in candidate:
            return "quattro"
        if "xdrive" in candidate:
            return "xdrive"
        return candidate

    def normalize_display_name(display_name: str, source_feature: str, raw_text: str):
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
        if _contains_forbidden_term(lowered):
            return None

        return display

    def validate_ai_feature_selection(payload, raw_text: str, max_headline: int = 3, max_additional: int = 6):
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
                    if len(accepted["headline_features"]) + len(accepted["additional_features"]) >= 3:
                        continue

                accepted[section].append(accepted_item)
                capability_seen.add(capability_key)

        return accepted

    def flatten_validated_features(validated):
        result = []
        for section in ("headline_features", "additional_features"):
            for item in validated.get(section, []):
                display_name = item.get("display_name_bg")
                if display_name and display_name not in result:
                    result.append(display_name)
        return result

    def build_short_accent(highlights):
        top_three = [item for item in (highlights or [])[:3] if item]
        return " | ".join(top_three)

    def build_short_accent_from_validated(validated):
        headline = [item.get("display_name_bg", "") for item in validated.get("headline_features", [])]
        return build_short_accent([item for item in headline if item])

    def remove_accent_duplicates(highlights, short_accent: str):
        accent_items = {
            _normalized_text(part)
            for part in (short_accent or "").split("|")
            if _normalized_text(part)
        }

        result = []
        for item in highlights or []:
            if _normalized_text(item) in accent_items:
                continue
            if item not in result:
                result.append(item)
        return result

SAVE_DIR = "encar_images"
MAX_IMAGES = 15
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://fem.encar.com/"
}

STATIC_FOOTER = """━━━━━━━━━━━━━━━━━━━
✅ Възможност за лизинг без първоначална вноска
✅ VIN проверка + пълен списък с екстри при интерес
✅ Доставка до 3–4 месеца – всичко организирано от нас
✅ Пълно съдействие до регистрация в България
━━━━━━━━━━━━━━━━━━━
📲 Следвайте ни във Facebook за още предложения
📞 Михаил: 0878 588 266
📞 Любо: 0877 56 77 52
📲 Присъединете се към нашата Viber група за още ексклузивни оферти:
👉 https://shorturl.at/11MsM"""


def format_eur(value):
    return f"{int(value):,}".replace(",", " ")


def format_km(value):
    if value is None:
        return "неуточнен пробег"
    return f"{int(value):,}".replace(",", " ")


def extract_price_krw(html):
    patterns = [
        r"([\d,]+)\s*만원",
        r"([\d,]+)\s*만\s*원",
        r'"price"\s*:\s*"?([\d,]+)"?',
        r'"advertisementPrice"\s*:\s*"?([\d,]+)"?',
        r'"sellPrice"\s*:\s*"?([\d,]+)"?',
        r'"carPrice"\s*:\s*"?([\d,]+)"?'
    ]

    for pattern in patterns:
        match = re.search(pattern, html)
        if not match:
            continue

        price_number = int(match.group(1).replace(",", ""))

        if "만" in match.group(0):
            return price_number * 10_000

        if price_number > 100000:
            return price_number

        return price_number * 10_000

    raise ValueError("Не успях да намеря цена в страницата.")


def extract_year(html):
    match = re.search(r"(\d{2})/\d{2}식", html)
    if not match:
        raise ValueError("Не успях да намеря година в страницата.")

    short_year = int(match.group(1))
    return 2000 + short_year if short_year < 80 else 1900 + short_year


def extract_mileage(html):
    match = re.search(r"([\d,]+)\s*km", html, re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else None


def calculate_extra_cost(base_price_eur, year):
    if year < 2022:
        return 6500 if base_price_eur <= 25000 else 7500

    if base_price_eur < 30000:
        return 7500

    if base_price_eur <= 50000:
        return 8000

    return 8500


def calculate_final_price_eur(base_price_eur, year):
    extra_cost = calculate_extra_cost(base_price_eur, year)
    total = base_price_eur + extra_cost
    final_price = math.ceil(total / 100) * 100
    return final_price, extra_cost


def extract_clean_car_text(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text("\n")
    lines = []

    for line in text.splitlines():
        line = line.strip()
        if line and len(line) >= 2:
            lines.append(line)

    return "\n".join(lines)[:12000]


def generate_facebook_data_with_openai(car_context):
    final_price = format_eur(car_context["final_price_eur"])
    mileage = format_km(car_context["mileage"])
    option_evidence_block = car_context.get("primary_option_evidence_block") or build_option_evidence_block(car_context["raw_car_text"])
    main_options_block = car_context.get("main_options_evidence_block") or "(няма основни опции)"
    ai_source_text = car_context.get("ai_source_text") or car_context["raw_car_text"]
    metadata = {
        "manufacturer": car_context.get("manufacturer"),
        "model": car_context.get("model"),
        "grade": car_context.get("grade"),
        "grade_detail": car_context.get("grade_detail"),
        "drivetrain_designation": car_context.get("drivetrain_designation"),
        "detail_query_car_id": (car_context.get("option_context") or {}).get("detail_query_car_id"),
        "vehicle_id": (car_context.get("option_context") or {}).get("vehicle_id"),
        "incomplete_data": (car_context.get("option_context") or {}).get("is_incomplete"),
    }

    prompt = f"""
Извлечи данни от Encar обява и върни само структурирани данни за публикация.

Върни САМО валиден JSON. Без markdown. Без обяснения.

JSON формат:
{{
  "title": "",
  "fuel": "",
  "transmission": "",
    "headline_features": [
        {{
            "source_feature": "",
            "display_name_bg": "",
            "reason": ""
        }}
    ],
    "additional_features": [
        {{
            "source_feature": "",
            "display_name_bg": "",
            "reason": ""
        }}
    ]
}}

ФАКТИ:
Крайна цена: {final_price} €
Година: {car_context["year"]}
Пробег: {mileage} KM
Производител: {metadata['manufacturer'] or 'unknown'}
Модел: {metadata['model'] or 'unknown'}
Ниво: {metadata['grade'] or 'unknown'}
Ниво детайл: {metadata['grade_detail'] or 'unknown'}
Точно задвижване: {metadata['drivetrain_designation'] or 'unknown'}
Detail query car id: {metadata['detail_query_car_id']}
Vehicle id: {metadata['vehicle_id']}

PRIMARY SOURCE (COMPLETE APPLIED OPTIONS FROM OPTION PAGE):
{option_evidence_block}

SECONDARY SOURCE (SHORT MAIN OPTIONS FROM DETAIL PAGE):
{main_options_block}

ПРАВИЛА:
- Пиши на български.
- title трябва да е пълно и продаваемо име.
- Избирай само характеристики, които са подкрепени от източниковите редове.
- Не измисляй и не извеждай характеристики, които не присъстват в източника.
- Разпознавай семантични еквиваленти и различни изписвания на една и съща екстра.
- Дай приоритет на редки, скъпи и силно продаваеми екстри за съответния модел.
- Деприоритизирай базови екстри (кожен салон, подгрев на предни седалки, автоматик, базов климатроник), но ги ползвай ако липсват по-силни.
- Не третирай история на ПТП, гаранция, import suitability, общо състояние и Encar warranty като екстри.
- Забранени generic фрази: "Премиум изпълнение", "Богато оборудване", "Отлична конфигурация", "Отлично оборудване", "Луксозно изпълнение", "Комфортен интериор", "Подходящ избор за внос", "Премиум автомобил", "Високо ниво на комфорт", "Богата конфигурация".
- Никога не използвай "Слънчев покрив".
- Използвай "Панорамен покрив" само при изрично panoramic roof.
- Използвай "Електрически люк" за normal sunroof.
- Запази manufacturer terms когато са налични: 4MATIC, quattro, xDrive, AIRMATIC, Distronic, Burmester, MULTIBEAM, S line.
- За Mercedes запази "4MATIC" (не го заменяй с "4x4 задвижване").
- За Audi запази "quattro".
- За BMW запази "xDrive".
- headline_features: до 3 елемента.
- additional_features: до 6 елемента.
- Не дублирай capability между headline_features и additional_features.
- reason е вътрешно поле и няма да се публикува.
- Ако има по-малко валидни екстри, върни по-малко; не добавяй пълнеж.
- transmission ако не е ясно, остави празно.
- title трябва да е пълно и продаваемо име, например Mercedes-AMG GLE53 4MATIC+ Coupe.

ТЕКСТ ОТ ОБЯВАТА:
{car_context["raw_car_text"]}
"""

    ai_feature_input = {
        "metadata": metadata,
        "primary_option_evidence_block": option_evidence_block,
        "main_options_evidence_block": main_options_block,
        "raw_car_text_length": len(car_context.get("raw_car_text") or ""),
        "options_passed_to_ai_count": len((car_context.get("option_context") or {}).get("applied_options") or []),
        "incomplete_data": metadata["incomplete_data"],
    }
    with open(os.path.join(SAVE_DIR, "ai_feature_input.json"), "w", encoding="utf-8") as f:
        json.dump(ai_feature_input, f, ensure_ascii=False, indent=2)

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    raw = response.output_text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"OpenAI не върна валиден JSON:\n{raw}")

    data = apply_fallbacks_and_filters(data, ai_source_text)
    with open(os.path.join(SAVE_DIR, "ai_feature_output.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def apply_fallbacks_and_filters(data, raw_car_text):
    title = (data.get("title") or "").strip()
    fuel = (data.get("fuel") or "").strip()
    transmission = (data.get("transmission") or "").strip()

    if not transmission:
        transmission = "Автоматик"

    if fuel.lower() in ["가솔린", "gasoline"]:
        fuel = "Бензин"

    if not fuel:
        fuel = "Бензин"

    if "GLE53" in title and "Mercedes" not in title:
        title = "Mercedes-AMG GLE53 4MATIC+ Coupe"

    validated = validate_ai_feature_selection(data, raw_car_text, max_headline=3, max_additional=6)
    selected_highlights = flatten_validated_features(validated)
    short_accent = build_short_accent_from_validated(validated)

    if not short_accent:
        short_accent = build_short_accent(selected_highlights)
    if not short_accent:
        short_accent = title

    data["title"] = title
    data["fuel"] = fuel.capitalize()
    data["transmission"] = transmission
    data["short_accent"] = short_accent
    data["strong_highlights"] = selected_highlights[:9]
    data["headline_features"] = validated.get("headline_features", [])
    data["additional_features"] = validated.get("additional_features", [])

    return data


def build_facebook_post(car_context, data):
    final_price = format_eur(car_context["final_price_eur"])
    mileage = format_km(car_context["mileage"])

    title = data.get("title") or "Автомобил от Южна Корея"
    fuel = data.get("fuel") or "Бензин"
    transmission = data.get("transmission") or "Автоматик"
    short_accent = data.get("short_accent") or title

    highlights = data.get("strong_highlights") or []
    highlights = remove_accent_duplicates(highlights, short_accent)

    final_highlights = []

    for item in highlights:
        if item not in final_highlights:
            final_highlights.append(item)

        if len(final_highlights) == 9:
            break

    lines = [
        f"💥 КРАЙНА ЦЕНА ДО БЪЛГАРИЯ: {final_price} € 💥",
        f"🚙 {title} 🚙",
        "━━━━━━━━━━━━━━━━━━━",
        f"⚜️ {car_context['year']} • 🖤 {mileage} KM",
        f"⛽ {fuel} | ⚙️ {transmission}",
        "━━━━━━━━━━━━━━━━━━━",
        f"💎 {short_accent}",
        "━━━━━━━━━━━━━━━━━━━",
    ]

    for item in final_highlights:
        lines.append(f"✅ {item}")

    lines.append("━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def print_price_summary(
    car_year,
    mileage,
    price_krw,
    base_price_eur,
    extra_cost,
    final_price_eur,
    krw_per_eur,
    exchange_rate_date,
):
    print(f"Exchange-rate source: {FRANKFURTER_SOURCE}")
    print(f"Exchange-rate date: {exchange_rate_date or 'unknown'}")
    print(f"EUR -> KRW rate: 1 EUR = {krw_per_eur:,.2f} KRW".replace(",", " "))
    print(f"Calculation: {price_krw:,} KRW / {krw_per_eur:,.2f}".replace(",", " "))
    print(f"Base vehicle price: {format_eur(round(base_price_eur))} EUR")
    print("━━━━━━━━━━━━━━━━━━━")
    print(f"Година: {car_year}")
    print(f"Пробег: {format_km(mileage)} km")
    print(f"Цена в Encar: {price_krw:,} KRW".replace(",", " "))
    print(f"Цена в Encar, превалутирана в евро: {format_eur(round(base_price_eur))} €")
    print(f"Добавена доставка/комисионна: {format_eur(extra_cost)} €")
    print(f"Крайна цена до България: {format_eur(final_price_eur)} €")
    print("━━━━━━━━━━━━━━━━━━━")


def download_images(html):
    matches = re.findall(r'https?:\\?/\\?/[^"\']+\.(?:jpg|jpeg|png)[^"\']*', html)

    images = []

    for match in matches:
        img_url = match.replace("\\/", "/")

        if "carpicture" not in img_url.lower():
            continue

        if img_url not in images:
            images.append(img_url)

    images = images[:MAX_IMAGES]

    print(f"Found {len(images)} images")

    for idx, img_url in enumerate(images, start=1):
        response = requests.get(img_url, headers=headers, timeout=30)
        response.raise_for_status()

        file_path = os.path.join(SAVE_DIR, f"{idx:02d}.jpg")

        with open(file_path, "wb") as f:
            f.write(response.content)

        print(f"Saved: {file_path}")


def main():
    while True:
        url = input("\nPaste Encar link, or press Enter to exit:\n> ").strip()

        if not url:
            print("Exit.")
            break

        print(f"Using URL: {url}")

        if os.path.exists(SAVE_DIR):
            shutil.rmtree(SAVE_DIR)

        os.makedirs(SAVE_DIR, exist_ok=True)

        print("Downloading page...")

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            html = response.text
        except requests.exceptions.ConnectionError:
            print("Грешка: Не мога да се свържа с Encar. Провери интернет, DNS или VPN.")
            continue
        except requests.exceptions.Timeout:
            print("Грешка: Encar не отговори навреме. Пробвай пак.")
            continue
        except requests.exceptions.RequestException as ex:
            print(f"Грешка при сваляне на страницата: {ex}")
            continue

        with open(os.path.join(SAVE_DIR, "debug_page.html"), "w", encoding="utf-8") as f:
            f.write(html)
        with open(os.path.join(SAVE_DIR, "detail_page.html"), "w", encoding="utf-8") as f:
            f.write(html)

        pricing_and_generation_succeeded = False

        try:
            print("Extracting price data...")

            price_krw = extract_price_krw(html)
            car_year = extract_year(html)
            mileage = extract_mileage(html)

            krw_per_eur, exchange_rate_date = get_eur_to_krw_rate_info()
            base_price_eur = krw_to_eur_with_rate(price_krw, krw_per_eur)
            final_price_eur, extra_cost = calculate_final_price_eur(base_price_eur, car_year)

            print_price_summary(
                car_year=car_year,
                mileage=mileage,
                price_krw=price_krw,
                base_price_eur=base_price_eur,
                extra_cost=extra_cost,
                final_price_eur=final_price_eur,
                krw_per_eur=krw_per_eur,
                exchange_rate_date=exchange_rate_date,
            )

            clean_car_text = extract_clean_car_text(html)
            option_context = extract_complete_option_context_from_detail_html(html, url)

            debug_artifacts = option_context.get("debug_artifacts") or {}
            detail_preloaded_state = debug_artifacts.get("detail_preloaded_state")
            if detail_preloaded_state is not None:
                with open(os.path.join(SAVE_DIR, "detail_preloaded_state.json"), "w", encoding="utf-8") as f:
                    json.dump(detail_preloaded_state, f, ensure_ascii=False, indent=2)

            option_page_html = debug_artifacts.get("option_page_html")
            if isinstance(option_page_html, str) and option_page_html:
                with open(os.path.join(SAVE_DIR, "option_page.html"), "w", encoding="utf-8") as f:
                    f.write(option_page_html)

            with open(os.path.join(SAVE_DIR, "all_option_entries.json"), "w", encoding="utf-8") as f:
                json.dump(option_context.get("all_option_entries") or [], f, ensure_ascii=False, indent=2)

            with open(os.path.join(SAVE_DIR, "applied_options.json"), "w", encoding="utf-8") as f:
                json.dump(option_context.get("applied_options") or [], f, ensure_ascii=False, indent=2)

            applied_evidence = build_applied_option_evidence_block(option_context)
            main_options_evidence = build_main_options_evidence_block(option_context)
            ai_source_text = "\n".join(
                [
                    "ПРИЛОЖЕНИ ОПЦИИ ОТ ENCAR OPTION PAGE:",
                    applied_evidence,
                    "",
                    "КРАТЪК MAIN OPTIONS БЛОК (SECONDARY):",
                    main_options_evidence,
                    "",
                    "ДОПЪЛНИТЕЛЕН ТЕКСТ ОТ ДЕТАЙЛ СТРАНИЦАТА:",
                    clean_car_text,
                ]
            )

            print(
                "Encar option extraction diagnostics: "
                f"detail_query_car_id={option_context.get('detail_query_car_id')} "
                f"vehicle_id={option_context.get('vehicle_id')} "
                f"total_options_displayed={option_context.get('total_options_displayed')} "
                f"applied_options_count={option_context.get('applied_options_count')} "
                f"unresolved_option_count={len(option_context.get('unresolved_option_codes') or [])} "
                f"options_passed_to_ai_count={len(option_context.get('applied_options') or [])} "
                f"incomplete={option_context.get('is_incomplete')}"
            )

            car_context = {
                "url": url,
                "year": car_year,
                "mileage": mileage,
                "price_krw": price_krw,
                "base_price_eur": round(base_price_eur),
                "extra_cost_eur": extra_cost,
                "final_price_eur": final_price_eur,
                "formatted_base_price_eur": format_eur(round(base_price_eur)),
                "formatted_final_price_eur": format_eur(final_price_eur),
                "formatted_mileage": format_km(mileage),
                "raw_car_text": clean_car_text,
                "ai_source_text": ai_source_text,
                "primary_option_evidence_block": applied_evidence,
                "main_options_evidence_block": main_options_evidence,
                "option_context": option_context,
                "manufacturer": (option_context.get("metadata") or {}).get("manufacturer"),
                "model": (option_context.get("metadata") or {}).get("model"),
                "grade": (option_context.get("metadata") or {}).get("grade"),
                "grade_detail": (option_context.get("metadata") or {}).get("grade_detail"),
                "drivetrain_designation": (option_context.get("metadata") or {}).get("drivetrain_designation"),
            }

            with open(os.path.join(SAVE_DIR, "vehicle_context.json"), "w", encoding="utf-8") as f:
                json.dump(car_context, f, ensure_ascii=False, indent=2)

            print("Generating Facebook data with OpenAI...")
            vehicle_data = generate_facebook_data_with_openai(car_context)

            facebook_post = build_facebook_post(car_context, vehicle_data)

            vehicle_data["facebook_post"] = facebook_post

            with open(os.path.join(SAVE_DIR, "vehicle_facts.json"), "w", encoding="utf-8") as f:
                json.dump(vehicle_data, f, ensure_ascii=False, indent=2)

            final_post = facebook_post.rstrip()

            while final_post.endswith("━━━━━━━━━━━━━━━━━━━"):
                final_post = final_post[:-19].rstrip()

            final_post = final_post + "\n" + STATIC_FOOTER

            with open(os.path.join(SAVE_DIR, "facebook_post.txt"), "w", encoding="utf-8") as f:
                f.write(final_post)

            print("Facebook post saved: encar_images/facebook_post.txt")
            pricing_and_generation_succeeded = True

        except Exception as ex:
            print(f"Грешка при извличане/генериране на описание: {ex}")
            print("Pricing/Facebook generation failed; image download will run independently.")

        if pricing_and_generation_succeeded:
            print("Downloading images...")
        else:
            print("Downloading images independently from pricing/post generation...")

        try:
            download_images(html)
        except Exception as ex:
            print(f"Грешка при сваляне на снимки: {ex}")

        print("Done.")


if __name__ == "__main__":
    main()
import json
from pathlib import Path

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL, STATIC_FOOTER
from .feature_selection import (
    build_option_evidence_block,
    build_short_accent,
    build_short_accent_from_validated,
    flatten_validated_features,
    remove_accent_duplicates,
    validate_ai_feature_selection,
)
from .pricing import format_eur, format_km

client = OpenAI(api_key=OPENAI_API_KEY)


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
Година: {car_context['year']}
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
{car_context['raw_car_text']}
"""

    debug_dir = car_context.get("debug_dir")
    if debug_dir:
        ai_feature_input = {
            "metadata": metadata,
            "primary_option_evidence_block": option_evidence_block,
            "main_options_evidence_block": main_options_block,
            "raw_car_text_length": len(car_context.get("raw_car_text") or ""),
            "options_passed_to_ai_count": len((car_context.get("option_context") or {}).get("applied_options") or []),
            "incomplete_data": metadata["incomplete_data"],
        }
        Path(debug_dir, "ai_feature_input.json").write_text(
            json.dumps(ai_feature_input, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    raw = response.output_text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"OpenAI не върна валиден JSON: {raw}")

    result = apply_fallbacks_and_filters(data, ai_source_text)

    if debug_dir:
        Path(debug_dir, "ai_feature_output.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return result


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

    final_post = "\n".join(lines)
    final_post = final_post + "\n" + STATIC_FOOTER

    return final_post

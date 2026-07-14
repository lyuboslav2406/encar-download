import json
from typing import Any


OLD_JSON_SCHEMA_EXAMPLE = {
    "title": "",
    "fuel": "",
    "transmission": "",
    "short_accent": "",
    "strong_highlights": [],
    "facebook_post": "",
}


def build_legacy_openai_prompt(car_context: dict[str, Any], final_price: str, mileage: str) -> str:
    schema = json.dumps(OLD_JSON_SCHEMA_EXAMPLE, ensure_ascii=False, indent=2)
    return f"""
От текста на Encar обява извлечи данни и създай Facebook пост за внос на автомобил.

Върни САМО валиден JSON. Без markdown. Без обяснения.

JSON формат:
{schema}

ЗАДЪЛЖИТЕЛНИ ДАННИ:
Крайна цена: {final_price} €
Година: {car_context["year"]}
Пробег: {mileage} KM

ФОРМАТ НА facebook_post:
💥 КРАЙНА ЦЕНА ДО БЪЛГАРИЯ: {final_price} € 💥
🚙 [title] 🚙
━━━━━━━━━━━━━━━━━━━
⚜️ {car_context["year"]} • 🖤 {mileage} KM
⛽ [fuel] | ⚙️ [transmission]
━━━━━━━━━━━━━━━━━━━
💎 [short_accent]
━━━━━━━━━━━━━━━━━━━
✅ характеристика
✅ характеристика
✅ характеристика
✅ характеристика
✅ характеристика
✅ характеристика
━━━━━━━━━━━━━━━━━━━

ПРАВИЛА:
- Пиши на български.
- Не добавяй линкове.
- Не добавяй телефони.
- Не добавяй VIN.
- Не добавяй доставка.
- Не добавяй лизинг.
- Не добавяй финални рекламни изречения.
- Не измисляй екстри.
- Ако не си сигурен за екстрата, не я включвай.
- transmission ако не е ясно, остави празно.
- title трябва да е пълно и продаваемо име, например Mercedes-AMG GLE53 4MATIC+ Coupe.
- short_accent да е 3 кратки акцента, разделени с |.
- strong_highlights да са 6 до 8 силни характеристики.
- facebook_post да използва най-силните 6 highlights.

НЕ включвай като highlights:
- климатик
- автоматичен климатик
- парктроник
- сензори за паркиране
- ел. стъкла
- смарт ключ
- ABS
- ESP
- airbags
- обикновена навигация
- обикновени LED фарове
- камера за заден ход, ако има по-силни характеристики

НЕ измисляй:
- premium audio
- Burmester
- Bang & Olufsen
- Harman Kardon
- Bose
- адаптивен круиз
- масажни седалки
- 360 камера
- head-up display
- Multibeam
ако тези думи не присъстват ясно в текста.

Ако моделът е AMG/M/RS, можеш да го използваш като характеристика, но не го наричай “спортен пакет”, освен ако не пише пакет.

ТЕКСТ ОТ ОБЯВАТА:
{car_context["raw_car_text"]}
"""


def apply_legacy_fallbacks_and_filters(data: dict[str, Any]) -> dict[str, Any]:
    title = (data.get("title") or "").strip()
    fuel = (data.get("fuel") or "").strip()
    transmission = (data.get("transmission") or "").strip()
    short_accent = (data.get("short_accent") or "").strip()
    highlights = data.get("strong_highlights") or []

    if not transmission:
        transmission = "Автоматик"

    if fuel.lower() in ["가솔린", "gasoline"]:
        fuel = "Бензин"

    if not fuel:
        fuel = "Бензин"

    if "GLE53" in title and "Mercedes" not in title:
        title = "Mercedes-AMG GLE53 4MATIC+ Coupe"

    weak_words = [
        "led фарове",
        "обикновени led",
        "парктроник",
        "сензори за паркиране",
        "камера за заден ход",
        "задна камера",
        "климатик",
        "автоматичен климатик",
        "смарт ключ",
        "abs",
        "esp",
        "airbag",
        "airbags",
        "ел. стъкла",
        "електрически стъкла",
        "навигация",
    ]

    filtered: list[str] = []

    for item in highlights:
        if not isinstance(item, str):
            continue

        item_clean = item.strip()
        item_lower = item_clean.lower()

        if any(weak in item_lower for weak in weak_words):
            continue

        if item_clean and item_clean not in filtered:
            filtered.append(item_clean)

    data["title"] = title
    data["fuel"] = fuel.capitalize()
    data["transmission"] = transmission
    data["short_accent"] = short_accent
    data["strong_highlights"] = filtered[:8]

    return data


def build_legacy_highlights(highlights: list[str]) -> list[str]:
    fallback_highlights = [
        "Премиум изпълнение",
        "Богато оборудване",
        "Отлична конфигурация",
        "Комфортен кожен салон",
        "Проверена история",
        "Подходящ избор за внос",
    ]

    final_highlights: list[str] = []

    for item in (highlights or []) + fallback_highlights:
        if item not in final_highlights:
            final_highlights.append(item)
        if len(final_highlights) == 6:
            break

    return final_highlights


def build_legacy_post_body(car_context: dict[str, Any], data: dict[str, Any], final_price: str, mileage: str) -> str:
    title = data.get("title") or "Автомобил от Южна Корея"
    fuel = data.get("fuel") or "Бензин"
    transmission = data.get("transmission") or "Автоматик"
    short_accent = data.get("short_accent") or title

    final_highlights = build_legacy_highlights(data.get("strong_highlights") or [])

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

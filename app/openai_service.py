import json

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL, STATIC_FOOTER
from .pricing import format_eur, format_km

client = OpenAI(api_key=OPENAI_API_KEY)


def apply_fallbacks_and_filters(data):
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

    weak_words = [
        "led фарове", "обикновени led", "парктроник", "сензори за паркиране",
        "камера за заден ход", "задна камера", "климатик", "автоматичен климатик",
        "смарт ключ", "abs", "esp", "airbag", "airbags", "ел. стъкла",
        "електрически стъкла", "навигация"
    ]

    filtered = []
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


def generate_facebook_data_with_openai(car_context):
    final_price = format_eur(car_context["final_price_eur"])
    mileage = format_km(car_context["mileage"])

    prompt = f"""
От текста на Encar обява извлечи данни и създай Facebook пост за внос на автомобил.

Върни САМО валиден JSON. Без markdown. Без обяснения.

JSON формат:
{{
  "title": "",
  "fuel": "",
  "transmission": "",
  "short_accent": "",
  "strong_highlights": []
}}

ЗАДЪЛЖИТЕЛНИ ДАННИ:
Крайна цена: {final_price} €
Година: {car_context['year']}
Пробег: {mileage} KM

ПРАВИЛА:
- Пиши на български.
- Не добавяй линкове.
- Не добавяй телефони.
- Не добавяй VIN.
- Не добавяй доставка.
- Не добавяй лизинг.
- Не измисляй екстри.
- Ако не си сигурен за екстрата, не я включвай.
- transmission ако не е ясно, остави празно.
- title трябва да е пълно и продаваемо име.
- short_accent да е 3 кратки акцента, разделени с |.
- strong_highlights да са 6 до 8 силни характеристики.

НЕ включвай слаби highlights:
климатик, парктроник, ел. стъкла, смарт ключ, ABS, ESP, airbags, обикновена навигация, камера за заден ход.

НЕ измисляй:
premium audio, Burmester, Bang & Olufsen, Harman Kardon, Bose, адаптивен круиз, масажни седалки, 360 камера, head-up display, Multibeam.

ТЕКСТ ОТ ОБЯВАТА:
{car_context['raw_car_text']}
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    raw = response.output_text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"OpenAI не върна валиден JSON: {raw}")

    return apply_fallbacks_and_filters(data)


def build_facebook_post(car_context, data):
    final_price = format_eur(car_context["final_price_eur"])
    mileage = format_km(car_context["mileage"])

    title = data.get("title") or "Автомобил от Южна Корея"
    fuel = data.get("fuel") or "Бензин"
    transmission = data.get("transmission") or "Автоматик"
    short_accent = data.get("short_accent") or title

    highlights = data.get("strong_highlights") or []

    fallback_highlights = [
        "Премиум изпълнение",
        "Богато оборудване",
        "Отлична конфигурация",
        "Комфортен кожен салон",
        "Проверена история",
        "Подходящ избор за внос"
    ]

    final_highlights = []
    for item in highlights + fallback_highlights:
        if item not in final_highlights:
            final_highlights.append(item)
        if len(final_highlights) == 6:
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

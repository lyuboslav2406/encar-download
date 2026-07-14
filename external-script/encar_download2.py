import json
import math
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import requests
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

try:
    from app.legacy_post_generation import (
        apply_legacy_fallbacks_and_filters,
        build_legacy_openai_prompt,
        build_legacy_post_body,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "app.legacy_post_generation"}:
        raise

    def build_legacy_openai_prompt(car_context: dict[str, Any], final_price: str, mileage: str) -> str:
        schema = json.dumps(
            {
                "title": "",
                "fuel": "",
                "transmission": "",
                "short_accent": "",
                "strong_highlights": [],
                "facebook_post": "",
            },
            ensure_ascii=False,
            indent=2,
        )
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

    def build_legacy_post_body(car_context: dict[str, Any], data: dict[str, Any], final_price: str, mileage: str) -> str:
        title = data.get("title") or "Автомобил от Южна Корея"
        fuel = data.get("fuel") or "Бензин"
        transmission = data.get("transmission") or "Автоматик"
        short_accent = data.get("short_accent") or title

        fallback_highlights = [
            "Премиум изпълнение",
            "Богато оборудване",
            "Отлична конфигурация",
            "Комфортен кожен салон",
            "Проверена история",
            "Подходящ избор за внос",
        ]

        final_highlights = []
        for item in (data.get("strong_highlights") or []) + fallback_highlights:
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

        lines.append("━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

SAVE_DIR = "encar_images"
MAX_IMAGES = 15
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://fem.encar.com/",
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
        r'"carPrice"\s*:\s*"?([\d,]+)"?',
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
    prompt = build_legacy_openai_prompt(car_context, final_price=final_price, mileage=mileage)

    response = client.responses.create(model=OPENAI_MODEL, input=prompt)
    raw = response.output_text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"OpenAI не върна валиден JSON:\n{raw}")

    return apply_fallbacks_and_filters(data)


def apply_fallbacks_and_filters(data):
    return apply_legacy_fallbacks_and_filters(data)


def build_facebook_post(car_context, data):
    final_price = format_eur(car_context["final_price_eur"])
    mileage = format_km(car_context["mileage"])
    return build_legacy_post_body(car_context, data, final_price=final_price, mileage=mileage)


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

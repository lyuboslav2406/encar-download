import os
import re
import json
import math
import shutil
import time
import zipfile
import uuid
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI


app = FastAPI()

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
GENERATED_DIR = BASE_DIR / "generated"

GENERATED_DIR.mkdir(exist_ok=True)

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


class GenerateRequest(BaseModel):
    url: str


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


def get_krw_to_eur_rate():
    url = "https://api.frankfurter.dev/v2/rates?base=KRW&quotes=EUR"

    response = requests.get(url, timeout=15)
    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):
        return data[0]["rate"]

    if isinstance(data, dict):
        if "rates" in data:
            return data["rates"]["EUR"]

        if "rate" in data:
            return data["rate"]

    raise Exception(f"Unexpected response: {data}")


def krw_to_eur(krw_price):
    rate = get_krw_to_eur_rate()
    return krw_price * rate


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
    lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) >= 2]
    return "\n".join(lines)[:12000]


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
Година: {car_context["year"]}
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
{car_context["raw_car_text"]}
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


def download_images(html, save_dir):
    matches = re.findall(r'https?:\\?/\\?/[^"\']+\.(?:jpg|jpeg|png)[^"\']*', html)

    images = []

    for match in matches:
        img_url = match.replace("\\/", "/")

        if "carpicture" not in img_url.lower():
            continue

        if img_url not in images:
            images.append(img_url)

    images = images[:MAX_IMAGES]
    saved_files = []

    for idx, img_url in enumerate(images, start=1):
        response = requests.get(img_url, headers=headers, timeout=30)
        response.raise_for_status()

        file_path = save_dir / f"{idx:02d}.jpg"

        with open(file_path, "wb") as f:
            f.write(response.content)

        saved_files.append(file_path)

    return saved_files


def create_zip(files, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file in files:
            zip_file.write(file, arcname=file.name)


def cleanup_old_jobs(max_age_hours=24, max_jobs=30):
    if not GENERATED_DIR.exists():
        return

    now = time.time()
    max_age_seconds = max_age_hours * 60 * 60

    job_dirs = [item for item in GENERATED_DIR.iterdir() if item.is_dir()]
    for job_dir in job_dirs:
        age_seconds = now - job_dir.stat().st_mtime
        if age_seconds > max_age_seconds:
            shutil.rmtree(job_dir, ignore_errors=True)

    job_dirs = [item for item in GENERATED_DIR.iterdir() if item.is_dir()]
    job_dirs.sort(key=lambda item: item.stat().st_mtime, reverse=True)

    for old_job in job_dirs[max_jobs:]:
        shutil.rmtree(old_job, ignore_errors=True)


def process_encar(url: str):
    cleanup_old_jobs(max_age_hours=24, max_jobs=30)
    job_id = str(uuid.uuid4())
    job_dir = GENERATED_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    html = response.text

    price_krw = extract_price_krw(html)
    car_year = extract_year(html)
    mileage = extract_mileage(html)

    base_price_eur = krw_to_eur(price_krw)
    final_price_eur, extra_cost = calculate_final_price_eur(base_price_eur, car_year)

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
        "raw_car_text": clean_car_text
    }

    vehicle_data = generate_facebook_data_with_openai(car_context)
    facebook_post = build_facebook_post(car_context, vehicle_data)

    image_files = download_images(html, job_dir)
    zip_path = job_dir / "encar_images.zip"
    create_zip(image_files, zip_path)

    price_summary = f"""━━━━━━━━━━━━━━━━━━━
Година: {car_year}
Пробег: {format_km(mileage)} km
Цена в Encar: {price_krw:,} KRW
Цена в Encar, превалутирана в евро: {format_eur(round(base_price_eur))} €
Добавена доставка/комисионна: {format_eur(extra_cost)} €
Крайна цена до България: {format_eur(final_price_eur)} €
━━━━━━━━━━━━━━━━━━━""".replace(",", " ")

    image_urls = [
        f"/image/{job_id}/{file.name}"
        for file in image_files
    ]

    return {
        "job_id": job_id,
        "price_summary": price_summary,
        "facebook_post": facebook_post,
        "zip_url": f"/download/{job_id}",
        "photos_url": f"/photos/{job_id}",
        "image_urls": image_urls,
        "images_count": len(image_files)
    }


@app.post("/generate")
def generate(request: GenerateRequest):
    try:
        result = process_encar(request.url)
        return result
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/download/{job_id}")
def download_zip(job_id: str):
    zip_path = GENERATED_DIR / job_id / "encar_images.zip"

    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP файлът не е намерен.")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="encar_images.zip"
    )


@app.get("/image/{job_id}/{image_name}")
def get_image(job_id: str, image_name: str):
    image_path = GENERATED_DIR / job_id / image_name

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Снимката не е намерена.")

    return FileResponse(
        image_path,
        media_type="image/jpeg",
        filename=image_name
    )


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
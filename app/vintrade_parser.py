"""Parser and image helpers for server-rendered VinTrade vehicle pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import HEADERS, MAX_IMAGES


VINTRADE_HOST = "vintrade.up.railway.app"
_MONEY_RE = re.compile(r"(?P<currency>€|\$|£)\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)")
_IMAGE_RE = re.compile(r"https?://[^\s\"'<>\\]+autoimg\.cn[^\s\"'<>\\]*", re.I)
_IMAGE_DIMENSION_RE = re.compile(r"/\d+x(?:\d+)?_")


@dataclass
class VinTradeVehicle:
    url: str
    title: str
    year: int | None
    mileage_km: int | None
    specifications: dict[str, str]
    prices: dict[str, dict[str, int | str] | None]
    image_urls: list[str]
    raw_text: str


def is_vintrade_url(url: str) -> bool:
    """Return whether a URL is hosted on VinTrade's listing domain."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and parsed.hostname == VINTRADE_HOST
    except (TypeError, ValueError):
        return False


def fetch_vintrade_html(url: str) -> str:
    response = requests.get(url, headers={**HEADERS, "Referer": f"https://{VINTRADE_HOST}/"}, timeout=30)
    response.raise_for_status()
    return response.text


def _text(element) -> str:
    return " ".join(element.stripped_strings)


def _money_after(text: str, label_pattern: str) -> dict[str, int | str] | None:
    label = re.search(label_pattern, text, re.I)
    if not label:
        return None
    match = _MONEY_RE.search(text[label.end():label.end() + 180])
    if not match:
        return None
    return {"amount": int(match.group("amount").replace(",", "")), "currency": match.group("currency")}


def _specifications(soup: BeautifulSoup) -> dict[str, str]:
    specs: dict[str, str] = {}
    for term in soup.select("main dt"):
        definition = term.find_next_sibling("dd")
        if not definition:
            continue
        key, value = _text(term), _text(definition)
        if key and value and key.lower() not in {"car price", "taxes to bulgaria"}:
            specs.setdefault(key, value)
    return specs


def _image_identity(url: str) -> str:
    return _IMAGE_DIMENSION_RE.sub("/", urlparse(url).path).lower()


def extract_gallery_images(html: str, expected_count: int | None = None) -> list[str]:
    """Choose one large URL per listing photo, excluding responsive duplicates."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main")
    if not main:
        return []

    # Gallery photos live in the labelled carousel region. This avoids logos,
    # listing cards, and the similar-car gallery elsewhere in <main>.
    gallery = next(
        (region for region in main.find_all(attrs={"aria-label": True})
         if re.search(r"photo|photos", region.get("aria-label", ""), re.I)),
        None,
    )
    if gallery is None:
        aside = main.find("aside")
        gallery = BeautifulSoup(str(main)[:str(main).find(str(aside))], "html.parser") if aside else main
    candidates: list[tuple[int, str]] = []
    for image in gallery.find_all("img"):
        urls = [image.get("src", "")]
        urls.extend(part.strip().split()[0] for part in image.get("srcset", "").split(",") if part.strip())
        for candidate in urls:
            if "autoimg.cn" not in candidate.lower():
                continue
            width_match = re.search(r"/(\d+)x(?:\d+)?_", candidate)
            candidates.append((int(width_match.group(1)) if width_match else 0, candidate))

    # Next.js serializes the full carousel as {"hd": ..., "thumb": ...}
    # records before similar-car cards. Prefer these verified high-resolution
    # URLs and use VinTrade's own gallery count to avoid similar-car records.
    normalized = unescape(html).replace("\\/", "/").replace("\\u002F", "/").replace('\\"', '"')
    hd_urls = re.findall(r'"hd"\s*:\s*"(https?://[^"\\]+)"', normalized, re.I)
    hd_urls = list(dict.fromkeys(url.replace("&amp;", "&") for url in hd_urls))
    if expected_count and len(hd_urls) >= expected_count:
        return hd_urls[: min(expected_count, MAX_IMAGES)]

    main_start = normalized.find("<main")
    sidebar_start = normalized.lower().find("<aside", main_start) if main_start >= 0 else -1
    gallery_html = normalized[main_start:sidebar_start] if main_start >= 0 and sidebar_start >= 0 else ""
    candidates.extend((0, match.group(0).replace("&amp;", "&")) for match in _IMAGE_RE.finditer(gallery_html))

    selected: dict[str, tuple[int, str]] = {}
    for width, candidate in candidates:
        if not candidate.startswith(("http://", "https://")):
            continue
        identity = _image_identity(candidate)
        current = selected.get(identity)
        if current is None or width > current[0]:
            selected[identity] = (width, candidate)
    return [item[1] for item in list(selected.values())[: min(expected_count or MAX_IMAGES, MAX_IMAGES)]]


def parse_vintrade_html(html: str, url: str) -> VinTradeVehicle:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    title_node = main.find("h1")
    title = _text(title_node) if title_node else ""
    specs = _specifications(main)
    text = _text(main)

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", title)
    if not year_match:
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", specs.get("First registered", ""))
    mileage_match = re.search(r"([\d,]+)\s*km\b", specs.get("Odometer", specs.get("Mileage", "")), re.I)
    if not mileage_match:
        mileage_match = re.search(r"([\d,]+)\s*km\b", text, re.I)

    asking_label = re.search(r"Asking price(?: in [\w ]+)?", text, re.I)
    asking_section = text[asking_label.end():asking_label.end() + 180] if asking_label else ""
    asking_values = list(_MONEY_RE.finditer(asking_section))
    rate_match = re.search(
        r"Rate on\s+(?P<date>[^:]+):\s*€\s*1\s*=\s*\$\s*(?P<rate>[\d.]+)",
        text,
        re.I,
    )
    prices = {
        "asking": ( {"amount": int(asking_values[0].group("amount").replace(",", "")), "currency": asking_values[0].group("currency")} if asking_values else None)
        or _money_after(text, r"\bCar price\b"),
        "asking_usd": next(
            ({"amount": int(match.group("amount").replace(",", "")), "currency": match.group("currency")} for match in asking_values if match.group("currency") == "$"),
            None,
        ),
        "taxes_to_bulgaria": _money_after(text, r"\bTaxes to Bulgaria\b"),
        "estimated_bulgaria": _money_after(text, r"\bEstimated price\b"),
        "eur_usd_rate": {"date": rate_match.group("date").strip(), "rate": float(rate_match.group("rate"))} if rate_match else None,
    }
    return VinTradeVehicle(
        url=url,
        title=title,
        year=int(year_match.group(1)) if year_match else None,
        mileage_km=int(mileage_match.group(1).replace(",", "")) if mileage_match else None,
        specifications=specs,
        prices=prices,
        image_urls=extract_gallery_images(
            html,
            expected_count=int(specs["Photos"]) if specs.get("Photos", "").isdigit() else None,
        ),
        raw_text=text[:12000],
    )


def _format_price(price: dict[str, int | str] | None) -> str | None:
    if not price:
        return None
    amount = f"{int(price['amount']):,}".replace(",", " ")
    return f"{price['currency']}{amount}"


def build_vintrade_post(vehicle: VinTradeVehicle) -> tuple[str, str]:
    """Build a grounded StreamLine Auto post and its displayed-price summary."""
    prices = vehicle.prices
    asking = _format_price(prices.get("asking"))
    asking_usd = _format_price(prices.get("asking_usd"))
    taxes = _format_price(prices.get("taxes_to_bulgaria"))
    estimate = _format_price(prices.get("estimated_bulgaria"))
    year = str(vehicle.year) if vehicle.year else "Година не е посочена"
    mileage = f"{vehicle.mileage_km:,}".replace(",", " ") if vehicle.mileage_km is not None else "неуточнен пробег"
    value_translations = {
        "electric": "Електрически",
        "automatic": "Автоматик",
        "rwd": "Задно предаване",
        "fwd": "Предно предаване",
        "awd": "Задвижване на всички колела",
        "sedan": "Седан",
        "suv": "SUV",
        "left-hand drive": "Ляв волан",
        "right-hand drive": "Десен волан",
    }

    def translated(value: str | None) -> str | None:
        return value_translations.get(value.lower(), value) if value else None

    fuel = translated(vehicle.specifications.get("Powertrain") or vehicle.specifications.get("Fuel"))
    gearbox = translated(vehicle.specifications.get("Gearbox"))
    drive = translated(vehicle.specifications.get("Drive"))
    body_style = translated(vehicle.specifications.get("Body style"))
    lines: list[str] = []

    if estimate:
        estimate_amount = f"{int(prices['estimated_bulgaria']['amount']):,}".replace(",", " ")
        estimate_currency = prices["estimated_bulgaria"]["currency"]
        post_estimate = f"{estimate_amount} {estimate_currency}"
        lines.append(f"💥 КРАЙНА ЦЕНА ДО БЪЛГАРИЯ: {post_estimate} 💥")
    elif asking:
        lines.append(f"💥 ЦЕНА В ОБЯВАТА: {asking} 💥")
    if vehicle.title:
        lines.append(f"🚙 {vehicle.title} 🚙")
    lines.extend(["━━━━━━━━━━━━━━━━━━━", f"⚜️ {year} • 🖤 {mileage} KM"])
    if fuel or gearbox:
        lines.append(f"⛽ {fuel or 'Гориво не е посочено'} | ⚙️ {gearbox or 'Трансмисия не е посочена'}")
    lines.append("━━━━━━━━━━━━━━━━━━━")

    accents = [value for value in (drive, body_style, vehicle.specifications.get("Trim")) if value]
    if accents:
        lines.extend([f"💎 {' | '.join(accents)}", "━━━━━━━━━━━━━━━━━━━"])
    labels = {
        "Power": "Мощност",
        "Battery": "Батерия",
        "Electric range": "Пробег на ток",
        "Fast charging": "Бързо зареждане",
        "Doors / seats": "Врати / места",
        "Dimensions": "Размери",
        "Curb weight": "Собствена маса",
        "Colour": "Цвят",
        "Steering": "Волан",
    }
    for key, label in labels.items():
        value = vehicle.specifications.get(key)
        if value:
            lines.append(f"✅ {label}: {translated(value) if key == 'Steering' else value}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("━━━━━━━━━━━━━━━━━━━")

    from .config import STATIC_FOOTER
    footer = STATIC_FOOTER.replace("✅ VIN проверка + пълен списък с екстри при интерес\n", "")
    post = "\n".join(lines) + "\n" + footer

    summary = ["Източник: VinTrade"]
    if vehicle.year:
        summary.append(f"Година: {vehicle.year}")
    summary.append(f"Пробег: {mileage} km")
    if asking:
        summary.append(f"Цена в обявата: {asking}")
    if asking_usd:
        summary.append(f"Цена в обявата в USD: {asking_usd}")
    if prices.get("eur_usd_rate"):
        rate = prices["eur_usd_rate"]
        summary.append(f"Курс по обявата ({rate['date']}): €1 = ${rate['rate']:.4f}")
    if taxes:
        summary.append(f"Данъци до България според обявата: {taxes}")
    if estimate:
        summary.append(f"Ориентировъчна цена до България според обявата: {estimate} (оценка, не оферта)")
    else:
        summary.append("Крайна цена не е изчислена.")
    return post, "\n".join(summary)


def get_vintrade_vehicle_title(vehicle: VinTradeVehicle) -> str | None:
    """Build a dashboard title from the listing title, trim and year only."""
    if not vehicle.title:
        return None
    title = re.sub(rf"^\s*{vehicle.year}\s+", "", vehicle.title, count=1) if vehicle.year else vehicle.title.strip()
    trim = vehicle.specifications.get("Trim", "").strip()
    trim = re.sub(r"^Model\s+", "", trim, flags=re.I)
    if trim and trim.casefold() not in title.casefold():
        title = f"{title} {trim}".strip()
    return f"{title} — {vehicle.year}" if vehicle.year else title


def download_vintrade_images(image_urls: list[str], save_dir) -> list:
    """Download gallery images and normalize them to JPEG for existing routes."""
    from io import BytesIO
    from pathlib import Path

    from PIL import Image

    saved = []
    for url in image_urls[:MAX_IMAGES]:
        response = requests.get(url, headers={**HEADERS, "Referer": f"https://{VINTRADE_HOST}/"}, timeout=30)
        response.raise_for_status()
        with Image.open(BytesIO(response.content)) as image:
            path = Path(save_dir) / f"{len(saved) + 1:02d}.jpg"
            image.convert("RGB").save(path, format="JPEG", quality=92, optimize=True)
        saved.append(path)
    return saved
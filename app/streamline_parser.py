"""Parser and post helpers for StreamLine Auto BG car listings."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import HEADERS, MAX_IMAGES
from .vintrade_parser import VinTradeVehicle, build_vintrade_post, download_vintrade_images


STREAMLINE_HOST = "streamlineautobg.com"
_PRICE_RE = re.compile(r"(?P<amount>[\d\s\u00a0\u202f,.]+)\s*(?P<currency>€|\$|£|лв\.?|EUR|USD|BGN)", re.I)
_IMAGE_DIMENSION_RE = re.compile(r"/(\d+)x(?:\d+)?_")
logger = logging.getLogger(__name__)


class StreamlineAccessError(requests.HTTPError):
    """The listing server denied or rejected an HTTP request."""


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _safe_response_excerpt(response: requests.Response) -> str:
    excerpt = " ".join(BeautifulSoup(response.text[:8192], "html.parser").stripped_strings)
    excerpt = re.sub(
        r"(?i)\b(authorization|cookie|set-cookie|token|csrf|api[_-]?key)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        excerpt,
    )
    return excerpt[:400]


def _diagnostic_headers(response: requests.Response) -> dict[str, str]:
    allowed = {"server", "cf-ray", "cf-cache-status", "cf-mitigated", "content-type", "retry-after"}
    return {key: value for key, value in response.headers.items() if key.lower() in allowed}


@dataclass
class StreamlineVehicle:
    url: str
    title: str
    make: str | None
    model: str | None
    year: int | None
    mileage_km: int | None
    fuel_type: str | None
    transmission: str | None
    engine: str | None
    specifications: dict[str, str]
    estimated_price_display: str
    image_urls: list[str]
    raw_text: str


def is_streamline_url(url: str) -> bool:
    """Return whether a URL points to a StreamLine Auto BG car listing."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme in {"http", "https"}
            and host in {STREAMLINE_HOST, f"www.{STREAMLINE_HOST}"}
            and parsed.path.startswith("/car/")
        )
    except (TypeError, ValueError):
        return False


def fetch_streamline_html(url: str) -> str:
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.25,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        response = session.get(
            url,
            headers={**HEADERS, "Referer": f"https://{STREAMLINE_HOST}/"},
            timeout=(10, 30),
            allow_redirects=True,
        )

    if response.status_code == 403:
        logger.warning(
            "StreamLine listing access denied: status=%s final_url=%s headers=%s body_excerpt=%r",
            response.status_code,
            _safe_url(response.url),
            _diagnostic_headers(response),
            _safe_response_excerpt(response),
        )
        raise StreamlineAccessError(
            f"StreamLine Auto BG denied the listing request (HTTP 403) at {_safe_url(response.url)}. "
            "This is an access restriction from the remote site; the listing could not be fetched."
        )

    response.raise_for_status()
    return response.text


def _text(element) -> str:
    return _normalize_space(" ".join(element.stripped_strings))


def _normalize_space(value: str) -> str:
    return re.sub(r"[\s\u00a0\u202f]+", " ", value).strip()


def _specifications(main) -> dict[str, str]:
    specs: dict[str, str] = {}
    for term in main.find_all("dt"):
        definition = term.find_next_sibling("dd")
        if not definition:
            continue
        key, value = _text(term), _text(definition)
        if key and value:
            specs.setdefault(key, value)
    return specs


def _schema_car(soup: BeautifulSoup) -> dict:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "Car":
                return item
    return {}


def _estimated_price(soup: BeautifulSoup) -> str:
    labels = {"очаквана цена до българия", "прогнозна цена"}
    for node in soup.find_all(string=True):
        if _normalize_space(str(node)).casefold() not in labels:
            continue
        sibling = node.parent.find_next_sibling() if node.parent else None
        candidates = [_text(sibling)] if sibling else []
        candidates.append(_text(node.parent.parent) if node.parent and node.parent.parent else "")
        for candidate in candidates:
            match = _PRICE_RE.search(_normalize_space(candidate))
            if match:
                return _normalize_space(match.group(0))
    raise ValueError("Не успях да извлека прогнозната цена от обявата на StreamLine Auto BG.")


def _image_identity(url: str) -> str:
    from urllib.parse import urlparse

    return _IMAGE_DIMENSION_RE.sub("/", urlparse(url).path).lower()


def _best_image_url(button) -> str | None:
    candidates: list[tuple[int, str]] = []
    for image in button.find_all("img"):
        src = image.get("src", "")
        if src:
            width = _IMAGE_DIMENSION_RE.search(src)
            candidates.append((int(width.group(1)) if width else 0, src))
        for part in image.get("srcset", "").split(","):
            match = re.match(r"\s*(\S+)\s+(\d+)w", part)
            if match:
                candidates.append((int(match.group(2)), match.group(1)))
    candidates = [(width, url) for width, url in candidates if "autoimg.cn" in url.lower()]
    return max(candidates, default=(0, ""), key=lambda item: item[0])[1] or None


def extract_streamline_images(html: str) -> list[str]:
    """Extract listing gallery images in carousel order, excluding similar cars."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    labels = [
        re.fullmatch(r"Снимка\s+1\s+от\s+(\d+)", button.get("aria-label", ""), re.I)
        for button in main.find_all("button", attrs={"aria-label": True})
    ]
    gallery_count = next((int(match.group(1)) for match in labels if match), None)
    if gallery_count is None:
        return []

    # Next.js streams the complete photo list as serialized high-resolution records.
    normalized = unescape(html).replace("\\/", "/").replace("\\u002F", "/").replace('\\"', '"')
    high_resolution = re.findall(r'"hd"\s*:\s*"(https?://[^"\\]+)"', normalized, re.I)
    high_resolution = list(dict.fromkeys(url.replace("&amp;", "&") for url in high_resolution))
    if len(high_resolution) >= gallery_count:
        return high_resolution[: min(gallery_count, MAX_IMAGES)]

    image_buttons = []
    for button in main.find_all("button", attrs={"aria-label": True}):
        match = re.fullmatch(r"Снимка\s+\d+\s+от\s+(\d+)", button.get("aria-label", ""), re.I)
        if match and int(match.group(1)) == gallery_count:
            image_buttons.append(button)

    ordered: dict[str, str] = {}
    for button in image_buttons:
        image_url = _best_image_url(button)
        if image_url:
            ordered.setdefault(_image_identity(image_url), image_url)
    return list(ordered.values())[: min(gallery_count, MAX_IMAGES)]


def parse_streamline_html(html: str, url: str) -> StreamlineVehicle:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    schema = _schema_car(soup)
    specs = _specifications(main)
    heading = main.find("h1")
    title = _text(heading) if heading else str(schema.get("name") or "")
    brand = schema.get("brand")
    make = brand.get("name") if isinstance(brand, dict) else (str(brand) if brand else None)
    model = str(schema.get("model") or "").strip() or None
    if not make and model and title.startswith(model):
        make = title[: len(title) - len(model)].strip() or None

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", specs.get("Година", "") or title)
    mileage_match = re.search(r"[\d\s\u00a0\u202f,.]+", specs.get("Пробег", ""))
    mileage = int(re.sub(r"\D", "", mileage_match.group(0))) if mileage_match else None
    fuel = specs.get("Гориво")
    transmission = specs.get("Скорости")
    engine = specs.get("Електромотор") or specs.get("Двигател") or specs.get("Мощност")
    estimated_price = _estimated_price(soup)

    return StreamlineVehicle(
        url=url,
        title=title,
        make=make,
        model=model,
        year=int(year_match.group(1)) if year_match else None,
        mileage_km=mileage,
        fuel_type=fuel,
        transmission=transmission,
        engine=engine,
        specifications=specs,
        estimated_price_display=estimated_price,
        image_urls=extract_streamline_images(html),
        raw_text=_text(main)[:12000],
    )


def _to_vintrade_vehicle(vehicle: StreamlineVehicle) -> VinTradeVehicle:
    """Adapt shared source-display fields for the existing post formatter."""
    specs_map = {
        "Задвижване": "Drive",
        "Каросерия": "Body style",
        "Гориво": "Powertrain",
        "Скорости": "Gearbox",
        "Мощност": "Power",
        "Батерия": "Battery",
        "Пробег на батерия": "Electric range",
        "Бързо зареждане": "Fast charging",
        "Врати / места": "Doors / seats",
        "Размери": "Dimensions",
        "Собствена маса": "Curb weight",
        "Цвят": "Colour",
    }
    mapped_specs = {specs_map.get(key, key): value for key, value in vehicle.specifications.items()}
    price_match = _PRICE_RE.search(vehicle.estimated_price_display)
    if not price_match:
        raise ValueError("Не успях да прочета прогнозната цена от обявата на StreamLine Auto BG.")
    numeric_amount = re.sub(r"\D", "", price_match.group("amount"))
    currency = price_match.group("currency")
    return VinTradeVehicle(
        url=vehicle.url,
        title=vehicle.title,
        year=vehicle.year,
        mileage_km=vehicle.mileage_km,
        specifications=mapped_specs,
        prices={
            "asking": None,
            "asking_usd": None,
            "taxes_to_bulgaria": None,
            "estimated_bulgaria": {"amount": int(numeric_amount), "currency": currency},
            "eur_usd_rate": None,
        },
        image_urls=vehicle.image_urls,
        raw_text=vehicle.raw_text,
    )


def build_streamline_post(vehicle: StreamlineVehicle) -> tuple[str, str]:
    """Build the existing post layout using only the listing's estimated price."""
    post, _ = build_vintrade_post(_to_vintrade_vehicle(vehicle))
    lines = post.splitlines()
    if lines:
        lines[0] = f"💥 КРАЙНА ЦЕНА ДО БЪЛГАРИЯ: {vehicle.estimated_price_display} 💥"
    summary = ["Източник: StreamLine Auto BG"]
    if vehicle.year:
        summary.append(f"Година: {vehicle.year}")
    if vehicle.mileage_km is not None:
        mileage = f"{vehicle.mileage_km:,}".replace(",", " ")
        summary.append(f"Пробег: {mileage} km")
    summary.append(f"Прогнозна цена според обявата: {vehicle.estimated_price_display}")
    return "\n".join(lines), "\n".join(summary)


def download_streamline_images(image_urls: list[str], save_dir) -> list:
    """Download the full StreamLine gallery in source order using shared conversion."""
    return download_vintrade_images(
        image_urls,
        save_dir,
        referer=f"https://{STREAMLINE_HOST}/",
    )

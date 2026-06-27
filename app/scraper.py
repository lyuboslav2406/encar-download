import re

import requests
from bs4 import BeautifulSoup

from .config import HEADERS


def download_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


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


def extract_clean_car_text(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) >= 2]
    return "\n".join(lines)[:12000]

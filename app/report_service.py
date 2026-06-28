import re

import requests
from bs4 import BeautifulSoup

from .config import HEADERS


def extract_carid_from_url(url: str) -> str:
    match = re.search(r"/cars/detail/([0-9]+)", url)
    if match:
        return match.group(1)

    match = re.search(r"/cars/report/accident/([0-9]+)", url)
    if match:
        return match.group(1)

    match = re.search(r"[?&]carid=(\d+)", url)
    if match:
        return match.group(1)

    return None


def extract_report_carid(html: str) -> str:
    carid = extract_carid_from_url(html)
    if carid:
        return carid

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    visible_text = soup.get_text("\n")

    patterns = [
        r"등록번호\s*[:：]?\s*([0-9]+)",
        r'"carid"\s*:\s*"([0-9]+)"',
        r'"carId"\s*:\s*"([0-9]+)"',
        r"carid\s*=\s*([0-9]+)",
    ]

    for pattern in patterns:
        for candidate in [html, visible_text]:
            match = re.search(pattern, candidate)
            if match:
                carid = match.group(1)
                print("Extracted report carid:", carid)
                return carid

    raise ValueError("Не успях да намеря регистрационен/репорт ID в страницата.")


def build_report_url(carid: str) -> str:
    return f"https://www.encar.com/md/sl/mdsl_regcar.do?method=inspectionViewNew&carid={carid}"


def build_insurance_url(carid: str) -> str:
    return f"https://fem.encar.com/cars/report/accident/{carid}"



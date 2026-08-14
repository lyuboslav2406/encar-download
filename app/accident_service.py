import re

from openai import OpenAI
from playwright.sync_api import sync_playwright

from .config import OPENAI_API_KEY, OPENAI_MODEL, HEADERS


def extract_car_id_from_url(url: str) -> str:
    match = re.search(r"/cars/detail/(\d+)", url)
    if not match:
        raise ValueError("Не успях да извлека car_id от URL.")
    return match.group(1)


def build_accident_url(car_id: str) -> str:
    return f"https://fem.encar.com/cars/report/accident/{car_id}"


def render_accident_page(accident_url: str) -> str:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(extra_http_headers=HEADERS)
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(accident_url, wait_until="networkidle", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=60000)
        page.wait_for_selector("body", timeout=30000)
        page.wait_for_timeout(5000)

        raw_text = page.evaluate(
            "() => {\n"
            "  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {\n"
            "    acceptNode(node) {\n"
            "      const parent = node.parentElement;\n"
            "      if (!parent) return NodeFilter.FILTER_REJECT;\n"
            "      const style = window.getComputedStyle(parent);\n"
            "      if (style && (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0')) return NodeFilter.FILTER_REJECT;\n"
            "      if (!node.textContent || !node.textContent.trim()) return NodeFilter.FILTER_REJECT;\n"
            "      return NodeFilter.FILTER_ACCEPT;\n"
            "    }\n"
            "  });\n"
            "  let text = '';\n"
            "  while (walker.nextNode()) {\n"
            "    text += walker.currentNode.textContent.trim() + '\\n';\n"
            "  }\n"
            "  return text;\n"
            "}"
        )

        if not raw_text or len(raw_text.strip()) < 20:
            raw_text = page.evaluate("() => document.documentElement.innerText")
        browser.close()
    return raw_text.strip()


def translate_accident_report_to_english(raw_text: str) -> str:
    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API key is not configured.")

    client = OpenAI(api_key=OPENAI_API_KEY)

    system_prompt = (
        "You are a translation assistant. Translate the supplied Korean accident and insurance report text into clean, literal English. "
        "Do not invent, summarize, or remove details. Preserve all accident records, insurance records, dates, owner changes, repair costs, KRW amounts, notes, and section structure. "
        "If any specific information is missing, write 'Not specified'. Output clean English suitable for sending to a client."
    )

    user_prompt = (
        "Translate the following Korean text exactly and faithfully into English:\n\n" + raw_text
    )

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_output_tokens=2048,
    )

    translation = getattr(response, 'output_text', None)
    if translation is None:
        translation = response.output[0].content[0].text.strip()

    return translation.strip()


def process_accident_report(url: str) -> dict:
    car_id = extract_car_id_from_url(url)
    accident_url = build_accident_url(car_id)
    raw_text = render_accident_page(accident_url)
    english_report = translate_accident_report_to_english(raw_text)

    return {
        "car_id": car_id,
        "accident_url": accident_url,
        "raw_text": raw_text,
        "english_report": english_report,
    }

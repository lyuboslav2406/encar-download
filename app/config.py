import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
GENERATED_DIR = BASE_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

MAX_IMAGES = 15
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

HEADERS = {
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

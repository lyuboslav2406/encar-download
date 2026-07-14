import json

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL, STATIC_FOOTER
from .legacy_post_generation import (
    apply_legacy_fallbacks_and_filters,
    build_legacy_openai_prompt,
    build_legacy_post_body,
)
from .pricing import format_eur, format_km

client = OpenAI(api_key=OPENAI_API_KEY)


def apply_fallbacks_and_filters(data, car_context):
    del car_context
    return apply_legacy_fallbacks_and_filters(data)


def generate_facebook_data_with_openai(car_context):
    final_price = format_eur(car_context["final_price_eur"])
    mileage = format_km(car_context["mileage"])
    prompt = build_legacy_openai_prompt(car_context, final_price=final_price, mileage=mileage)

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    raw = response.output_text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"OpenAI не върна валиден JSON:\n{raw}")

    return apply_fallbacks_and_filters(data, car_context)


def build_facebook_post(car_context, data):
    final_price = format_eur(car_context["final_price_eur"])
    mileage = format_km(car_context["mileage"])
    post_body = build_legacy_post_body(car_context, data, final_price=final_price, mileage=mileage)

    final_post = post_body.rstrip()
    while final_post.endswith("━━━━━━━━━━━━━━━━━━━"):
        final_post = final_post[:-19].rstrip()

    return final_post + "\n" + STATIC_FOOTER

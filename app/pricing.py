import math
from typing import Any

import requests


FRANKFURTER_SOURCE = "Frankfurter"
FRANKFURTER_EUR_KRW_URL = "https://api.frankfurter.dev/v2/rate/EUR/KRW"
MIN_PLAUSIBLE_KRW_PER_EUR = 500
MAX_PLAUSIBLE_KRW_PER_EUR = 5000


class ExchangeRateError(ValueError):
    pass


def format_eur(value):
    return f"{int(value):,}".replace(",", " ")


def format_km(value):
    if value is None:
        return "неуточнен пробег"
    return f"{int(value):,}".replace(",", " ")


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


def get_eur_to_krw_rate() -> float:
    krw_per_eur, _ = get_eur_to_krw_rate_info()
    return krw_per_eur


def krw_to_eur_with_rate(krw_price: int | float, krw_per_eur: float) -> float:
    validated_krw_per_eur = _validate_krw_per_eur(krw_per_eur)
    return float(krw_price) / validated_krw_per_eur


def krw_to_eur(krw_price: int | float) -> float:
    krw_per_eur = get_eur_to_krw_rate()
    return krw_to_eur_with_rate(krw_price, krw_per_eur)


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

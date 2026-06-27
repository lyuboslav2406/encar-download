import math

import requests


def format_eur(value):
    return f"{int(value):,}".replace(",", " ")


def format_km(value):
    if value is None:
        return "неуточнен пробег"
    return f"{int(value):,}".replace(",", " ")


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

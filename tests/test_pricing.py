import unittest
from unittest.mock import patch

from app.pricing import (
    ExchangeRateError,
    FRANKFURTER_EUR_KRW_URL,
    get_eur_to_krw_rate_info,
    krw_to_eur,
    krw_to_eur_with_rate,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class PricingTests(unittest.TestCase):
    @staticmethod
    def valid_payload(rate=1700.0):
        return {
            "date": "2026-07-13",
            "base": "EUR",
            "quote": "KRW",
            "rate": rate,
        }

    def test_krw_to_eur_divides_by_rate_1700(self):
        result = krw_to_eur_with_rate(39_900_000, 1_700)
        self.assertAlmostEqual(result, 23_470.588, places=3)

    def test_krw_to_eur_divides_by_rate_1720_12(self):
        result = krw_to_eur_with_rate(39_900_000, 1_720.12)
        self.assertAlmostEqual(result, 23_195.82, delta=1.0)
        self.assertAlmostEqual(result, 39_900_000 / 1_720.12, places=8)

    def test_krw_to_eur_divides_not_multiplies(self):
        krw_per_eur = 1_700
        result = krw_to_eur_with_rate(39_900_000, krw_per_eur)
        wrong_multiply_result = 39_900_000 * krw_per_eur

        self.assertAlmostEqual(result, 39_900_000 / krw_per_eur, places=8)
        self.assertNotEqual(result, wrong_multiply_result)

    @patch("app.pricing.requests.get")
    def test_get_eur_to_krw_rate_info_parses_single_rate_shape(self, mock_get):
        mock_get.return_value = FakeResponse(self.valid_payload(rate=1720.12))

        krw_per_eur, rate_date = get_eur_to_krw_rate_info()

        self.assertEqual(krw_per_eur, 1720.12)
        self.assertEqual(rate_date, "2026-07-13")
        mock_get.assert_called_once_with(FRANKFURTER_EUR_KRW_URL, timeout=15)

    @patch("app.pricing.requests.get")
    def test_reject_list_response_shape(self, mock_get):
        mock_get.return_value = FakeResponse([self.valid_payload(rate=1720.12)])

        with self.assertRaises(ExchangeRateError):
            get_eur_to_krw_rate_info()

    @patch("app.pricing.requests.get")
    def test_reject_wrong_base(self, mock_get):
        payload = self.valid_payload(rate=1720.12)
        payload["base"] = "USD"
        mock_get.return_value = FakeResponse(payload)

        with self.assertRaises(ExchangeRateError):
            get_eur_to_krw_rate_info()

    @patch("app.pricing.requests.get")
    def test_reject_wrong_quote(self, mock_get):
        payload = self.valid_payload(rate=1720.12)
        payload["quote"] = "JPY"
        mock_get.return_value = FakeResponse(payload)

        with self.assertRaises(ExchangeRateError):
            get_eur_to_krw_rate_info()

    @patch("app.pricing.requests.get")
    def test_old_rounded_direct_rate_regression_and_direction(self, mock_get):
        old_wrong_result = 39_900_000 * 0.00058
        self.assertEqual(old_wrong_result, 23_142.0)

        mock_get.return_value = FakeResponse(self.valid_payload(rate=1720.12))

        result = krw_to_eur(39_900_000)
        called_url = mock_get.call_args[0][0]

        self.assertAlmostEqual(result, 23_195.82, delta=1.0)
        self.assertAlmostEqual(result, 39_900_000 / 1_720.12, places=8)
        self.assertTrue(called_url.endswith("/v2/rate/EUR/KRW"))
        self.assertNotIn("/v2/rates", called_url)

    @patch("app.pricing.requests.get")
    def test_regression_old_rates_list_shape_fails_and_new_endpoint_is_used(self, mock_get):
        mock_get.return_value = FakeResponse([
            {
                "date": "2026-07-13",
                "base": "EUR",
                "quote": "KRW",
                "rate": 1684.25,
            }
        ])

        with self.assertRaisesRegex(ExchangeRateError, "Unexpected exchange-rate response type: list"):
            get_eur_to_krw_rate_info()

        called_url = mock_get.call_args[0][0]
        self.assertTrue(called_url.endswith("/v2/rate/EUR/KRW"))

    def test_reject_invalid_rate_values(self):
        invalid_values = [0, -1, 499.99, 5000.01, "1720", None]

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ExchangeRateError):
                    krw_to_eur_with_rate(39_900_000, value)

    @patch("app.pricing.requests.get")
    def test_reject_missing_rate(self, mock_get):
        payload = self.valid_payload(rate=1720.12)
        payload.pop("rate")
        mock_get.return_value = FakeResponse(payload)

        with self.assertRaises(ExchangeRateError):
            get_eur_to_krw_rate_info()

    @patch("app.pricing.requests.get")
    def test_reject_non_numeric_rate(self, mock_get):
        mock_get.return_value = FakeResponse(self.valid_payload(rate="bad-value"))

        with self.assertRaises(ExchangeRateError):
            get_eur_to_krw_rate_info()

    @patch("app.pricing.requests.get")
    def test_reject_boolean_rate(self, mock_get):
        mock_get.return_value = FakeResponse(self.valid_payload(rate=True))

        with self.assertRaises(ExchangeRateError):
            get_eur_to_krw_rate_info()

    @patch("app.pricing.requests.get")
    def test_reject_nan_rate(self, mock_get):
        mock_get.return_value = FakeResponse(self.valid_payload(rate=float("nan")))

        with self.assertRaises(ExchangeRateError):
            get_eur_to_krw_rate_info()

    @patch("app.pricing.requests.get")
    def test_reject_infinite_rate(self, mock_get):
        mock_get.return_value = FakeResponse(self.valid_payload(rate=float("inf")))

        with self.assertRaises(ExchangeRateError):
            get_eur_to_krw_rate_info()

    @patch("app.pricing.requests.get")
    def test_reject_implausibly_low_or_high_rate(self, mock_get):
        for bad_rate in [100, 10_000]:
            with self.subTest(bad_rate=bad_rate):
                mock_get.return_value = FakeResponse(self.valid_payload(rate=bad_rate))

                with self.assertRaises(ExchangeRateError):
                    get_eur_to_krw_rate_info()

    @patch("app.pricing.requests.get")
    def test_preserves_rate_date(self, mock_get):
        mock_get.return_value = FakeResponse(self.valid_payload(rate=1700.0))

        _, rate_date = get_eur_to_krw_rate_info()
        self.assertEqual(rate_date, "2026-07-13")


if __name__ == "__main__":
    unittest.main()

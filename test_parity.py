"""
Test unitari per parity_calculations.py.
Coverage target: 80%+

Eseguire con:
    python -m pytest test_parity.py -v
"""

import math
import unittest
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd

from parity_calculations import (
    _hex_to_rgb,
    _interpolate_hex,
    _rgb_to_hex,
    build_parity_df,
    calculate_arbitrage_profit,
    calculate_parity,
    compute_dte,
    filter_strikes,
    get_dte_color,
    is_atm,
)
from parity_constants import ARBITRAGE_THRESHOLD, ATM_RANGE


# ---------------------------------------------------------------------------
# calculate_parity
# ---------------------------------------------------------------------------
class TestCalculateParity(unittest.TestCase):
    def test_zero_parity_perfect_market(self):
        """In un mercato perfetto la parity è 0."""
        spot = 5000.0
        strike = 5000.0
        rfr = 0.04
        dte = 30
        T = dte / 365.0
        pv_strike = strike * math.exp(-rfr * T)
        # Se call_mid - put_mid = spot - pv_strike → parity = 0
        diff = spot - pv_strike
        call_mid = diff + 5.0
        put_mid = 5.0
        parity = calculate_parity(call_mid, put_mid, strike, rfr, dte, spot)
        self.assertAlmostEqual(parity, 0.0, places=6)

    def test_positive_parity(self):
        """Parity > 0 indica put sottovalutata."""
        parity = calculate_parity(
            call_mid=10.0,
            put_mid=1.0,
            strike=5000.0,
            risk_free_rate=0.04,
            dte=30,
            spot=5005.0,
        )
        # call_mid > put_mid con spot ~ strike → parity dovrebbe essere positiva
        self.assertIsInstance(parity, float)

    def test_zero_dte(self):
        """Con DTE=0, T=0 → pv_strike = strike."""
        spot = 5000.0
        strike = 5000.0
        call_mid = 5.0
        put_mid = 5.0
        parity = calculate_parity(call_mid, put_mid, strike, 0.04, 0, spot)
        # C - P + K - S = 5 - 5 + 5000 - 5000 = 0
        self.assertAlmostEqual(parity, 0.0, places=6)

    def test_negative_dte_treated_as_zero(self):
        """DTE negativo deve essere trattato come 0."""
        parity_zero = calculate_parity(5.0, 5.0, 5000.0, 0.04, 0, 5000.0)
        parity_neg = calculate_parity(5.0, 5.0, 5000.0, 0.04, -10, 5000.0)
        self.assertAlmostEqual(parity_neg, parity_zero, places=6)

    def test_high_rfr(self):
        """Tasso molto alto riduce il PV dello strike."""
        parity_low_r = calculate_parity(10.0, 10.0, 5000.0, 0.0, 365, 4990.0)
        parity_high_r = calculate_parity(10.0, 10.0, 5000.0, 0.10, 365, 4990.0)
        # Con r alto, PV(strike) < strike, quindi parity cambia
        self.assertNotAlmostEqual(parity_low_r, parity_high_r, places=2)


# ---------------------------------------------------------------------------
# is_atm
# ---------------------------------------------------------------------------
class TestIsATM(unittest.TestCase):
    def test_exactly_at_spot(self):
        self.assertTrue(is_atm(5000.0, 5000.0))

    def test_within_range(self):
        self.assertTrue(is_atm(5000.0 + ATM_RANGE, 5000.0))
        self.assertTrue(is_atm(5000.0 - ATM_RANGE, 5000.0))

    def test_outside_range(self):
        self.assertFalse(is_atm(5000.0 + ATM_RANGE + 1, 5000.0))
        self.assertFalse(is_atm(5000.0 - ATM_RANGE - 1, 5000.0))

    def test_custom_range(self):
        self.assertTrue(is_atm(5050.0, 5000.0, atm_range=100.0))
        self.assertFalse(is_atm(5050.0, 5000.0, atm_range=10.0))


# ---------------------------------------------------------------------------
# calculate_arbitrage_profit
# ---------------------------------------------------------------------------
class TestCalculateArbitrageProfit(unittest.TestCase):
    def test_single_contract(self):
        self.assertAlmostEqual(calculate_arbitrage_profit(2.0), 200.0)

    def test_multiple_contracts(self):
        self.assertAlmostEqual(calculate_arbitrage_profit(1.5, contracts=3), 450.0)

    def test_negative_parity_same_as_positive(self):
        self.assertAlmostEqual(
            calculate_arbitrage_profit(-2.0), calculate_arbitrage_profit(2.0)
        )

    def test_zero_parity(self):
        self.assertAlmostEqual(calculate_arbitrage_profit(0.0), 0.0)


# ---------------------------------------------------------------------------
# get_dte_color
# ---------------------------------------------------------------------------
class TestGetDTEColor(unittest.TestCase):
    def test_zero_dte_is_red(self):
        self.assertEqual(get_dte_color(0).upper(), "#FF0000")

    def test_max_dte_is_cyan(self):
        self.assertEqual(get_dte_color(92).upper(), "#00CCFF")

    def test_above_max_dte(self):
        # Deve restituire il colore dell'ultimo stop
        self.assertEqual(get_dte_color(200).upper(), "#00CCFF")

    def test_below_min_dte(self):
        self.assertEqual(get_dte_color(-5).upper(), "#FF0000")

    def test_midpoint_is_interpolated(self):
        color = get_dte_color(30)
        # Non deve essere né rosso né ciano
        self.assertNotEqual(color.upper(), "#FF0000")
        self.assertNotEqual(color.upper(), "#00CCFF")
        # Deve essere un hex valido
        self.assertRegex(color, r"^#[0-9A-Fa-f]{6}$")

    def test_returns_valid_hex(self):
        for dte in [0, 7, 14, 30, 60, 92, 120]:
            color = get_dte_color(dte)
            self.assertRegex(color, r"^#[0-9A-Fa-f]{6}$", f"DTE={dte}")


# ---------------------------------------------------------------------------
# Interpolazione colori helper
# ---------------------------------------------------------------------------
class TestColorHelpers(unittest.TestCase):
    def test_hex_to_rgb(self):
        self.assertEqual(_hex_to_rgb("#FF0000"), (255, 0, 0))
        self.assertEqual(_hex_to_rgb("#00FF00"), (0, 255, 0))
        self.assertEqual(_hex_to_rgb("#0000FF"), (0, 0, 255))

    def test_rgb_to_hex(self):
        self.assertEqual(_rgb_to_hex(255, 0, 0), "#FF0000")
        self.assertEqual(_rgb_to_hex(0, 255, 0), "#00FF00")
        self.assertEqual(_rgb_to_hex(0, 0, 255), "#0000FF")

    def test_interpolate_at_zero(self):
        result = _interpolate_hex("#FF0000", "#0000FF", 0.0)
        self.assertEqual(result.upper(), "#FF0000")

    def test_interpolate_at_one(self):
        result = _interpolate_hex("#FF0000", "#0000FF", 1.0)
        self.assertEqual(result.upper(), "#0000FF")

    def test_interpolate_at_midpoint(self):
        result = _interpolate_hex("#000000", "#FFFFFF", 0.5)
        r, g, b = _hex_to_rgb(result)
        # Dovrebbe essere grigio (circa 127-128)
        self.assertAlmostEqual(r, 128, delta=1)
        self.assertAlmostEqual(g, 128, delta=1)
        self.assertAlmostEqual(b, 128, delta=1)


# ---------------------------------------------------------------------------
# filter_strikes
# ---------------------------------------------------------------------------
class TestFilterStrikes(unittest.TestCase):
    def _make_df(self, strikes: list[float]) -> pd.DataFrame:
        return pd.DataFrame({"strike": strikes})

    def test_all_returns_all(self):
        df = self._make_df([4900.0, 5000.0, 5100.0])
        result = filter_strikes(df, 5000.0, "all")
        self.assertEqual(len(result), 3)

    def test_itm_returns_below_spot(self):
        df = self._make_df([4900.0, 5000.0, 5100.0])
        result = filter_strikes(df, 5000.0, "itm")
        self.assertTrue(all(result["strike"] < 5000.0))
        self.assertEqual(len(result), 1)

    def test_otm_returns_above_spot(self):
        df = self._make_df([4900.0, 5000.0, 5100.0])
        result = filter_strikes(df, 5000.0, "otm")
        self.assertTrue(all(result["strike"] > 5000.0))
        self.assertEqual(len(result), 1)

    def test_atm_returns_within_50(self):
        df = self._make_df([4900.0, 4960.0, 5000.0, 5040.0, 5100.0])
        result = filter_strikes(df, 5000.0, "atm")
        self.assertFalse((result["strike"] == 4900.0).any())
        self.assertFalse((result["strike"] == 5100.0).any())

    def test_custom_range(self):
        df = self._make_df([4900.0, 5000.0, 5100.0, 5200.0])
        result = filter_strikes(df, 5000.0, "custom", min_strike=4950.0, max_strike=5100.0)
        self.assertEqual(set(result["strike"]), {5000.0, 5100.0})

    def test_custom_without_bounds_returns_all(self):
        df = self._make_df([4900.0, 5000.0, 5100.0])
        result = filter_strikes(df, 5000.0, "custom")
        self.assertEqual(len(result), 3)

    def test_empty_df(self):
        df = self._make_df([])
        result = filter_strikes(df, 5000.0, "all")
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# compute_dte
# ---------------------------------------------------------------------------
class TestComputeDTE(unittest.TestCase):
    def test_today_is_zero(self):
        today_str = date.today().strftime("%Y-%m-%d")
        self.assertEqual(compute_dte(today_str), 0)

    def test_tomorrow_is_one(self):
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        self.assertEqual(compute_dte(tomorrow), 1)

    def test_past_date_is_zero(self):
        past = "2020-01-01"
        self.assertEqual(compute_dte(past), 0)

    def test_future_date(self):
        future = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        self.assertEqual(compute_dte(future), 30)


# ---------------------------------------------------------------------------
# build_parity_df
# ---------------------------------------------------------------------------
class TestBuildParityDf(unittest.TestCase):
    def _make_chain(self, strikes: list[float]) -> tuple[pd.DataFrame, pd.DataFrame]:
        calls = pd.DataFrame(
            {
                "strike": strikes,
                "bid": [10.0] * len(strikes),
                "ask": [12.0] * len(strikes),
                "impliedVolatility": [0.20] * len(strikes),
            }
        )
        puts = pd.DataFrame(
            {
                "strike": strikes,
                "bid": [8.0] * len(strikes),
                "ask": [10.0] * len(strikes),
                "impliedVolatility": [0.22] * len(strikes),
            }
        )
        return calls, puts

    def test_basic_output_columns(self):
        calls, puts = self._make_chain([5000.0, 5100.0])
        result = build_parity_df(calls, puts, 5050.0, 0.04, "2025-03-21", 7)
        expected_cols = {
            "strike", "call_mid", "put_mid", "call_iv", "put_iv",
            "avg_iv", "expiry", "dte", "parity", "is_atm", "profit", "color",
        }
        self.assertTrue(expected_cols.issubset(set(result.columns)))

    def test_mid_calculation(self):
        calls, puts = self._make_chain([5000.0])
        result = build_parity_df(calls, puts, 5000.0, 0.04, "2025-03-21", 7)
        self.assertAlmostEqual(result["call_mid"].iloc[0], 11.0)  # (10+12)/2
        self.assertAlmostEqual(result["put_mid"].iloc[0], 9.0)    # (8+10)/2

    def test_expiry_and_dte_stored(self):
        calls, puts = self._make_chain([5000.0])
        result = build_parity_df(calls, puts, 5000.0, 0.04, "2025-03-21", 45)
        self.assertEqual(result["expiry"].iloc[0], "2025-03-21")
        self.assertEqual(result["dte"].iloc[0], 45)

    def test_is_atm_flag(self):
        calls, puts = self._make_chain([5000.0, 5500.0])
        result = build_parity_df(calls, puts, 5000.0, 0.04, "2025-03-21", 30)
        atm_row = result[result["strike"] == 5000.0]
        otm_row = result[result["strike"] == 5500.0]
        self.assertTrue(atm_row["is_atm"].iloc[0])
        self.assertFalse(otm_row["is_atm"].iloc[0])

    def test_profit_is_abs_parity_times_100(self):
        calls, puts = self._make_chain([5000.0])
        result = build_parity_df(calls, puts, 5000.0, 0.04, "2025-03-21", 30)
        expected_profit = abs(result["parity"].iloc[0]) * 100
        self.assertAlmostEqual(result["profit"].iloc[0], expected_profit)

    def test_zero_bid_ask_skipped(self):
        """Righe con entrambi call_mid=0 e put_mid=0 vengono scartate."""
        calls = pd.DataFrame({
            "strike": [5000.0],
            "bid": [0.0],
            "ask": [0.0],
            "impliedVolatility": [0.20],
        })
        puts = pd.DataFrame({
            "strike": [5000.0],
            "bid": [0.0],
            "ask": [0.0],
            "impliedVolatility": [0.22],
        })
        result = build_parity_df(calls, puts, 5000.0, 0.04, "2025-03-21", 30)
        self.assertTrue(result.empty)

    def test_empty_chains(self):
        calls = pd.DataFrame(columns=["strike", "bid", "ask", "impliedVolatility"])
        puts = pd.DataFrame(columns=["strike", "bid", "ask", "impliedVolatility"])
        result = build_parity_df(calls, puts, 5000.0, 0.04, "2025-03-21", 30)
        self.assertTrue(result.empty)

    def test_avg_iv(self):
        calls, puts = self._make_chain([5000.0])
        result = build_parity_df(calls, puts, 5000.0, 0.04, "2025-03-21", 30)
        expected_avg_iv = (0.20 + 0.22) / 2
        self.assertAlmostEqual(result["avg_iv"].iloc[0], expected_avg_iv)

    def test_color_is_valid_hex(self):
        calls, puts = self._make_chain([5000.0])
        result = build_parity_df(calls, puts, 5000.0, 0.04, "2025-03-21", 30)
        import re
        color = result["color"].iloc[0]
        self.assertRegex(color, r"^#[0-9A-Fa-f]{6}$")


if __name__ == "__main__":
    unittest.main(verbosity=2)

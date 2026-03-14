"""
Funzioni di calcolo per l'analisi Put/Call Parity.

Formula centrale:
    Parity = CallMid - PutMid + Strike * exp(-r * T) - Spot

In un mercato efficiente Parity ≈ 0.
Un valore significativamente diverso da zero segnala un'opportunità di arbitraggio.
"""

import math
from datetime import date, datetime

import pandas as pd

from parity_constants import ATM_RANGE, DTE_COLOR_STOPS


# ---------------------------------------------------------------------------
# Calcolo Parity
# ---------------------------------------------------------------------------

def calculate_parity(
    call_mid: float,
    put_mid: float,
    strike: float,
    risk_free_rate: float,
    dte: int,
    spot: float,
) -> float:
    """
    Calcola la deviazione dalla Put/Call Parity.

    Args:
        call_mid: Prezzo mid della call (bid+ask)/2.
        put_mid:  Prezzo mid della put  (bid+ask)/2.
        strike:   Strike price.
        risk_free_rate: Tasso risk-free (es. 0.04 per 4%).
        dte:      Days to expiration.
        spot:     Prezzo spot del sottostante.

    Returns:
        Deviazione dalla parity ($). 0 = parity perfetta.
    """
    T = max(dte, 0) / 365.0
    pv_strike = strike * math.exp(-risk_free_rate * T)
    return call_mid - put_mid + pv_strike - spot


# ---------------------------------------------------------------------------
# Identificazione ATM
# ---------------------------------------------------------------------------

def is_atm(strike: float, spot: float, atm_range: float = ATM_RANGE) -> bool:
    """True se lo strike è entro atm_range punti dallo spot."""
    return abs(strike - spot) <= atm_range


# ---------------------------------------------------------------------------
# Colore gradiente DTE
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(int(round(r)), int(round(g)), int(round(b)))


def _interpolate_hex(c0: str, c1: str, t: float) -> str:
    r0, g0, b0 = _hex_to_rgb(c0)
    r1, g1, b1 = _hex_to_rgb(c1)
    return _rgb_to_hex(r0 + t * (r1 - r0), g0 + t * (g1 - g0), b0 + t * (b1 - b0))


def get_dte_color(dte: int) -> str:
    """
    Restituisce un colore hex interpolato in base ai DTE.

    Gradiente: rosso (0 DTE) → arancio → giallo → verde → ciano-blu (92+ DTE).
    """
    stops = DTE_COLOR_STOPS
    if dte <= stops[0][0]:
        return stops[0][1]
    if dte >= stops[-1][0]:
        return stops[-1][1]
    for i in range(len(stops) - 1):
        d0, c0 = stops[i]
        d1, c1 = stops[i + 1]
        if d0 <= dte <= d1:
            t = (dte - d0) / (d1 - d0)
            return _interpolate_hex(c0, c1, t)
    return stops[-1][1]


# ---------------------------------------------------------------------------
# Filtro strikes
# ---------------------------------------------------------------------------

def filter_strikes(
    df: pd.DataFrame,
    spot: float,
    filter_type: str,
    min_strike: float | None = None,
    max_strike: float | None = None,
) -> pd.DataFrame:
    """
    Filtra il DataFrame in base al tipo di strike.

    Args:
        df:          DataFrame con colonna 'strike'.
        spot:        Prezzo spot.
        filter_type: 'all' | 'itm' | 'atm' | 'otm' | 'custom'.
        min_strike:  Limite inferiore per filtro 'custom'.
        max_strike:  Limite superiore per filtro 'custom'.

    Returns:
        DataFrame filtrato.
    """
    if filter_type == "itm":
        # ITM calls = strike < spot
        return df[df["strike"] < spot]
    elif filter_type == "atm":
        return df[df["strike"].apply(lambda k: is_atm(k, spot, atm_range=50))]
    elif filter_type == "otm":
        # OTM calls = strike > spot
        return df[df["strike"] > spot]
    elif filter_type == "custom" and min_strike is not None and max_strike is not None:
        return df[(df["strike"] >= min_strike) & (df["strike"] <= max_strike)]
    return df  # 'all'


# ---------------------------------------------------------------------------
# Profit da arbitraggio
# ---------------------------------------------------------------------------

def calculate_arbitrage_profit(parity: float, contracts: int = 1) -> float:
    """
    Stima il profitto lordo per ogni punto di arbitraggio.

    Profit = |parity| × 100 × contracts
    (moltiplicatore standard futures/opzioni S&P = 100)
    """
    return abs(parity) * 100 * contracts


# ---------------------------------------------------------------------------
# Costruzione DataFrame parity (merge calls + puts)
# ---------------------------------------------------------------------------

def compute_dte(expiry_str: str) -> int:
    """Calcola i DTE a partire da una stringa data 'YYYY-MM-DD'."""
    today = date.today()
    exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    return max(0, (exp - today).days)


def build_parity_df(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    spot: float,
    risk_free_rate: float,
    expiration_date: str,
    dte: int,
) -> pd.DataFrame:
    """
    Unisce calls e puts per strike e calcola la parity per ogni coppia.

    Args:
        calls_df:        DataFrame calls da yfinance (con colonne bid, ask, strike, impliedVolatility).
        puts_df:         DataFrame puts da yfinance.
        spot:            Prezzo spot.
        risk_free_rate:  Tasso risk-free (0.04 = 4%).
        expiration_date: Stringa data scadenza 'YYYY-MM-DD'.
        dte:             Days to expiration.

    Returns:
        DataFrame con colonne:
            strike, call_mid, put_mid, call_iv, put_iv, avg_iv,
            expiry, dte, parity, is_atm, profit, color
    """
    # --- Calls ---
    calls = calls_df[["strike", "bid", "ask", "impliedVolatility"]].copy()
    calls["call_mid"] = (calls["bid"] + calls["ask"]) / 2.0
    calls["call_iv"] = calls["impliedVolatility"].fillna(0.0)
    calls = calls[["strike", "call_mid", "call_iv"]]

    # --- Puts ---
    puts = puts_df[["strike", "bid", "ask", "impliedVolatility"]].copy()
    puts["put_mid"] = (puts["bid"] + puts["ask"]) / 2.0
    puts["put_iv"] = puts["impliedVolatility"].fillna(0.0)
    puts = puts[["strike", "put_mid", "put_iv"]]

    # --- Merge su strike ---
    merged = pd.merge(calls, puts, on="strike", how="inner")

    # Scarta righe illiquide (entrambi i mid a zero)
    merged = merged[(merged["call_mid"] > 0) | (merged["put_mid"] > 0)]

    if merged.empty:
        return merged

    # --- Calcolo parity ---
    merged["expiry"] = str(expiration_date)
    merged["dte"] = dte
    merged["parity"] = merged.apply(
        lambda r: calculate_parity(
            r["call_mid"], r["put_mid"], r["strike"], risk_free_rate, dte, spot
        ),
        axis=1,
    )
    merged["is_atm"] = merged["strike"].apply(lambda k: is_atm(k, spot))
    merged["profit"] = merged["parity"].apply(calculate_arbitrage_profit)
    merged["avg_iv"] = (merged["call_iv"] + merged["put_iv"]) / 2.0
    merged["color"] = get_dte_color(dte)

    return merged

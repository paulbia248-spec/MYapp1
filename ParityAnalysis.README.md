# Put/Call Parity Analysis — Integration Guide

## Overview

The **Put/Call Parity Analysis** tab integrates into the GEX QUANT PRO Streamlit app as a new
sub-section inside the **IV Term** tab. It detects deviations from put/call parity in real-time
option chains fetched from Yahoo Finance, highlighting potential arbitrage opportunities.

### Put/Call Parity Formula

```
Parity = CallMid − PutMid + Strike × e^(−r × T) − Spot
```

| Symbol | Meaning |
|--------|---------|
| `CallMid` | Mid price of the call option `(bid + ask) / 2` |
| `PutMid`  | Mid price of the put option `(bid + ask) / 2` |
| `Strike`  | Strike price |
| `r`       | Annualized risk-free rate |
| `T`       | Time to expiration in years (`DTE / 365`) |
| `Spot`    | Current underlying price |

**Efficient market:** Parity ≈ 0
**Arbitrage signal:** |Parity| > $1.00 (configurable via `ARBITRAGE_THRESHOLD`)

---

## File Structure

```
MYapp1/
├── app.py                    # Main app — modified to use st.tabs() + IV Term tab
├── parity_tab.py             # Streamlit component: render_parity_tab()
├── parity_calculations.py    # Pure Python calculation functions
├── parity_constants.py       # Shared constants
├── test_parity.py            # Unit tests (pytest)
└── ParityAnalysis.README.md  # This file
```

---

## Props / API

### `render_parity_tab()` — `parity_tab.py`

Self-contained Streamlit renderer. No arguments required; data is fetched internally
via Yahoo Finance and stored in `st.session_state`.

**Internal state keys used:**

| Key | Type | Description |
|-----|------|-------------|
| `parity_ready` | `bool` | True after successful data load |
| `parity_spot` | `float` | Current spot price |
| `parity_expirations` | `list[str]` | Available expiry dates |
| `parity_sym` | `str` | Current ticker symbol |
| `parity_df` | `pd.DataFrame` | Computed parity data (all expiries) |

---

### `parity_calculations.py` — Function Reference

```python
calculate_parity(call_mid, put_mid, strike, risk_free_rate, dte, spot) -> float
```
Returns the deviation from put/call parity in dollars.

```python
is_atm(strike, spot, atm_range=ATM_RANGE) -> bool
```
Returns `True` if the strike is within `atm_range` points of spot.

```python
get_dte_color(dte) -> str
```
Returns a hex color string interpolated across the DTE gradient.

```python
filter_strikes(df, spot, filter_type, min_strike=None, max_strike=None) -> pd.DataFrame
```
Filters the parity DataFrame. `filter_type` ∈ `{'all', 'itm', 'atm', 'otm', 'custom'}`.

```python
calculate_arbitrage_profit(parity, contracts=1) -> float
```
Estimates gross arbitrage profit: `|parity| × 100 × contracts`.

```python
compute_dte(expiry_str) -> int
```
Returns days to expiration from a `"YYYY-MM-DD"` string.

```python
build_parity_df(calls_df, puts_df, spot, risk_free_rate, expiration_date, dte) -> pd.DataFrame
```
Merges call and put DataFrames by strike and computes all parity metrics.

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `strike` | float | Strike price |
| `call_mid` | float | Call mid price |
| `put_mid` | float | Put mid price |
| `call_iv` | float | Call implied volatility |
| `put_iv` | float | Put implied volatility |
| `avg_iv` | float | Average IV (call+put)/2 |
| `expiry` | str | Expiration date string |
| `dte` | int | Days to expiration |
| `parity` | float | Parity deviation ($) |
| `is_atm` | bool | True if within ATM_RANGE of spot |
| `profit` | float | Estimated arbitrage profit ($) |
| `color` | str | Hex color for DTE gradient |

---

### `parity_constants.py` — Constants Reference

| Constant | Default | Description |
|----------|---------|-------------|
| `ARBITRAGE_THRESHOLD` | `1.0` | Min |parity| ($) to trigger alert |
| `ATM_RANGE` | `25.0` | Points around spot for ATM classification |
| `MAX_EXPIRIES` | `10` | Maximum selectable expirations |
| `MAX_POINTS` | `1000` | Max chart points (performance cap) |
| `DTE_COLOR_STOPS` | see file | List of `(dte, hex_color)` tuples for gradient |

---

## Integration Steps

### 1. Install dependencies

```bash
pip install -r requirements.txt
# For PNG export:
pip install kaleido
```

### 2. Import in `app.py`

```python
from parity_tab import render_parity_tab
```

### 3. Add IV Term tab

```python
tab_csv, tab_live, tab_iv = st.tabs(["📂 GEX – CSV", "🌐 GEX – Live", "📊 IV Term"])

with tab_iv:
    render_parity_tab()
```

---

## UI Components

### Scatter Chart
- **X axis:** Strike price ($)
- **Y axis:** Parity deviation ($)
- **Color:** DTE gradient — red (0 DTE) → orange → yellow → green → cyan-blue (92+ DTE)
- **Size:** 12px for ATM strikes (±25pt), 6px for others
- **Border:** 3px green border on ATM strikes
- **Overlays:**
  - Vertical dashed green line at Spot
  - Horizontal dotted red/blue lines at ±$1.00 (toggleable)

### Alert Panel
Shows arbitrage opportunities where |parity| > $1.00, sorted by profit descending.
- **Priority HIGH:** |parity| > $2.00 or profit > $500
- **Strategy steps:** Buy/sell put → hedge call → futures direction
- Limited to top 20 for performance; full count shown

### Metrics Panel (10 cards)
Spot Price · Date · Expiries Selected · Strikes Visible · Strikes ATM ·
Alert Count · Parity Min · Parity Max · Avg IV · Risk-Free Rate

### Export
| Button | Output |
|--------|--------|
| CSV Dati | Full parity DataFrame as `.csv` |
| PNG Grafico | High-res chart image (requires kaleido) |
| URL Shareable | Query-string link with current configuration |

---

## Running Tests

```bash
python -m pytest test_parity.py -v
```

Expected output: **30+ tests**, coverage **>80%** of `parity_calculations.py`.

---

## Performance Notes

- Option chain data is **cached 5 minutes** via `@st.cache_data(ttl=300)`
- Chart subsampled to **max 1000 points** if data exceeds limit
- Alert panel shows **max 20 items** with virtual scroll via `st.expander`
- Slider updates are debounced by Streamlit's native on-release behavior

---

## Theming

The component uses Plotly's `plotly_dark` template for the chart, and injects a
`<style>` block with CSS variables matching the app's dark color palette:

```css
--parity-bg:       #0a0a0a
--parity-card-bg:  #111111
--parity-primary:  #00ff88
--parity-text:     #e0e0e0
--parity-muted:    #888888
--parity-border:   #1a1a1a
--parity-danger:   #ff4444
--parity-warning:  #ffaa00
--parity-success:  #00cc66
```

---

## Responsive Layout

| Viewport | Layout |
|----------|--------|
| Desktop (>1024px) | Chart full width · Alert + Metrics in 2 columns |
| Mobile (<768px) | Single column stack (handled by Streamlit's responsive grid) |

---

## Accessibility

- All interactive controls have descriptive labels and `help` tooltips
- `st.metric` components include contextual delta indicators
- Alert expanders use descriptive titles for screen readers
- Color contrast follows WCAG AA guidelines (dark background + light text)

---

## Testing Checklist

- [ ] Data connection loads without error for SPY/QQQ/IWM
- [ ] Selecting 1 expiry shows correct chart
- [ ] Selecting 5+ expiries all appear with distinct DTE colors
- [ ] ITM/ATM/OTM filter buttons reduce visible strikes correctly
- [ ] Slider range restricts strikes in real-time
- [ ] ATM strikes display at 12px with green border
- [ ] ±$1.00 threshold lines appear/disappear with toggle
- [ ] Alert panel sorted by profit descending
- [ ] Tooltip shows all required fields including ⚠️ if |parity|>1
- [ ] Metrics update after applying new expiry selection
- [ ] Layout renders correctly at 1920, 1024, 768, 375px
- [ ] Chart colors match DTE gradient (red→cyan-blue)
- [ ] CSV export downloads valid file
- [ ] PNG export works (kaleido installed)
- [ ] Keyboard navigation through all controls

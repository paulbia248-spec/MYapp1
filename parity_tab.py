"""
Componente Streamlit: Put/Call Parity Analysis Tab.

Uso in app.py:
    from parity_tab import render_parity_tab
    render_parity_tab()
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from parity_calculations import (
    build_parity_df,
    calculate_arbitrage_profit,
    compute_dte,
    filter_strikes,
    get_dte_color,
)
from parity_constants import ARBITRAGE_THRESHOLD, ATM_RANGE, MAX_EXPIRIES, MAX_POINTS

# ---------------------------------------------------------------------------
# CSS personalizzato (usa CSS vars Streamlit / plotly_dark)
# ---------------------------------------------------------------------------
_CUSTOM_CSS = """
<style>
:root {
    --parity-bg:        #0a0a0a;
    --parity-card-bg:   #111111;
    --parity-primary:   #00ff88;
    --parity-text:      #e0e0e0;
    --parity-muted:     #888888;
    --parity-border:    #1a1a1a;
    --parity-danger:    #ff4444;
    --parity-warning:   #ffaa00;
    --parity-success:   #00cc66;
}

/* Card metriche */
div[data-testid="metric-container"] {
    background: var(--parity-card-bg);
    border: 1px solid var(--parity-border);
    border-radius: 8px;
    padding: 10px 14px;
}

/* Alert HIGH */
.parity-alert-high {
    border-left: 4px solid var(--parity-danger) !important;
}

/* Alert MED */
.parity-alert-med {
    border-left: 4px solid var(--parity-warning) !important;
}

/* Badge */
.parity-badge-high {
    background: var(--parity-danger);
    color: #fff;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.8em;
    font-weight: bold;
}
.parity-badge-med {
    background: var(--parity-warning);
    color: #000;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.8em;
    font-weight: bold;
}
</style>
"""


# ---------------------------------------------------------------------------
# Fetch dati (cached per evitare richieste ridondanti)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_spot_and_expirations(ticker_sym: str) -> tuple[float, list[str]]:
    """Recupera spot price e lista scadenze disponibili."""
    tk = yf.Ticker(ticker_sym)
    hist = tk.history(period="1d")
    if hist.empty:
        raise ValueError(f"Nessun dato storico per {ticker_sym}")
    spot = float(hist["Close"].iloc[-1])
    expirations = list(tk.options)[:MAX_EXPIRIES]
    return spot, expirations


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_chain(ticker_sym: str, expiration: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recupera la catena opzioni per una scadenza specifica."""
    tk = yf.Ticker(ticker_sym)
    chain = tk.option_chain(expiration)
    return chain.calls, chain.puts


# ---------------------------------------------------------------------------
# Grafico scatter Parity
# ---------------------------------------------------------------------------

def _build_parity_chart(
    plot_df: pd.DataFrame,
    spot: float,
    ticker_sym: str,
    show_arb_lines: bool,
) -> go.Figure:
    fig = go.Figure()

    for exp in sorted(plot_df["expiry"].unique()):
        exp_data = plot_df[plot_df["expiry"] == exp].copy()
        dte_val = int(exp_data["dte"].iloc[0])
        color = get_dte_color(dte_val)

        atm_mask = exp_data["is_atm"]

        for subset, size, border_col, border_w, name_suffix in [
            (exp_data[~atm_mask], 6,  color,     1, ""),
            (exp_data[atm_mask],  12, "#00FF88",  3, " ★ATM"),
        ]:
            if subset.empty:
                continue

            hover = subset.apply(
                lambda r: (
                    f"<b>Strike: ${r['strike']:,.0f}</b><br>"
                    f"Scadenza: {r['expiry']}<br>"
                    f"DTE: {r['dte']}g<br>"
                    f"Parity: ${r['parity']:.4f}<br>"
                    f"Call Mid: ${r['call_mid']:.2f}<br>"
                    f"Put Mid:  ${r['put_mid']:.2f}<br>"
                    f"IV Media: {r['avg_iv']*100:.1f}%<br>"
                    f"Spot: ${spot:,.2f}"
                    + (
                        "<br><b>⚠️ "
                        + ("Put sopravvalutata" if r["parity"] > 0 else "Put sottovalutata")
                        + "</b>"
                        if abs(r["parity"]) > ARBITRAGE_THRESHOLD
                        else ""
                    )
                ),
                axis=1,
            )

            fig.add_trace(
                go.Scatter(
                    x=subset["strike"],
                    y=subset["parity"],
                    mode="markers",
                    name=f"{exp} ({dte_val}d){name_suffix}",
                    marker=dict(
                        size=size,
                        color=color,
                        line=dict(color=border_col, width=border_w),
                        opacity=0.88,
                    ),
                    text=hover,
                    hovertemplate="%{text}<extra></extra>",
                )
            )

    # Linea verticale SPOT
    fig.add_vline(
        x=spot,
        line_dash="dash",
        line_color="#00FF88",
        line_width=2,
        annotation_text=f"SPOT ${spot:,.2f}",
        annotation_font_color="#00FF88",
    )

    # Soglie arbitraggio ±$1.00
    if show_arb_lines:
        fig.add_hline(
            y=ARBITRAGE_THRESHOLD,
            line_dash="dot",
            line_color="#FF4444",
            line_width=1.5,
            annotation_text=f"+${ARBITRAGE_THRESHOLD:.2f}",
            annotation_font_color="#FF4444",
            annotation_position="right",
        )
        fig.add_hline(
            y=-ARBITRAGE_THRESHOLD,
            line_dash="dot",
            line_color="#4488FF",
            line_width=1.5,
            annotation_text=f"-${ARBITRAGE_THRESHOLD:.2f}",
            annotation_font_color="#4488FF",
            annotation_position="right",
        )

    fig.update_layout(
        title=f"Put/Call Parity — {ticker_sym}",
        template="plotly_dark",
        xaxis_title="Strike ($)",
        yaxis_title="Deviazione dalla Parity ($)",
        xaxis_tickformat="$,.0f",
        yaxis_tickformat="$.2f",
        height=540,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
        margin=dict(t=80, b=40, l=60, r=80),
        paper_bgcolor="#0a0a0a",
        plot_bgcolor="#0a0a0a",
    )
    return fig


# ---------------------------------------------------------------------------
# Pannello Alert
# ---------------------------------------------------------------------------

def _render_alert_panel(full_df: pd.DataFrame) -> None:
    st.markdown("### ⚠️ Alert Arbitraggio")

    alerts = full_df[full_df["parity"].abs() > ARBITRAGE_THRESHOLD].copy()
    alerts = alerts.sort_values("profit", ascending=False)

    if alerts.empty:
        st.success("✓ Mercato Efficiente — Nessun arbitraggio rilevato")
        return

    total = len(alerts)
    if total > 20:
        st.info(f"Top 20 di {total} alert trovati")
        alerts = alerts.head(20)

    for _, row in alerts.iterrows():
        is_high = abs(row["parity"]) > 2.0 or row["profit"] > 500
        badge = "🔴 HIGH" if is_high else "🟡 MED"

        # Direzione e strategia
        if row["parity"] > 0:
            # Call > Put  → put sottovalutata → compra put, vendi call, short futures
            direction = "Put sottovalutata"
            put_action = "**Compra** Put"
            call_action = "**Vendi** Call"
            fut_action = "**Short** /ES"
        else:
            # Put > Call  → call sottovalutata → compra call, vendi put, long futures
            direction = "Call sottovalutata"
            put_action = "**Vendi** Put"
            call_action = "**Compra** Call"
            fut_action = "**Long** /ES"

        with st.expander(
            f"{badge} | Strike ${row['strike']:,.0f} | {row['expiry']} | Profitto: ${row['profit']:.0f}"
        ):
            st.markdown(
                f"**DTE:** {row['dte']}g &nbsp;|&nbsp; "
                f"**Parity:** ${row['parity']:.4f} &nbsp;|&nbsp; "
                f"**Situazione:** {direction}"
            )
            st.markdown(
                f"""
**Strategia di arbitraggio:**
1. 📋 Opzioni: {put_action} @ ${row['strike']:,.0f}
2. 🔄 Hedge:   {call_action} @ ${row['strike']:,.0f}
3. 📈 Futures: {fut_action}

---
🛡️ **Rischio: Limitato** &nbsp;|&nbsp; ⚠️ *Verifica liquidità prima di eseguire*
"""
            )


# ---------------------------------------------------------------------------
# Pannello Metriche
# ---------------------------------------------------------------------------

def _render_metrics_panel(
    full_df: pd.DataFrame,
    plot_df: pd.DataFrame,
    spot: float,
    rfr: float,
    selected_expiries: list[str],
) -> None:
    st.markdown("### 📊 Metriche")

    n_atm = int(full_df["is_atm"].sum())
    n_alerts = int((full_df["parity"].abs() > ARBITRAGE_THRESHOLD).sum())
    parity_min = full_df["parity"].min()
    parity_max = full_df["parity"].max()
    avg_iv = full_df["avg_iv"].mean() * 100

    cols = st.columns(2)
    metrics = [
        ("📍 Spot Price",           f"${spot:,.2f}",                             None),
        ("📅 Data",                 date.today().strftime("%d/%m/%Y"),            None),
        ("📆 Scadenze Sel.",        str(len(selected_expiries)),                  None),
        ("📊 Strikes Visualizzati", str(len(plot_df)),                            None),
        ("🎯 Strikes ATM",          str(n_atm),                                  f"±{ATM_RANGE:.0f}pt"),
        ("⚠️ Alert Arbitraggio",   str(n_alerts),                                "HIGH" if n_alerts > 0 else None),
        ("📉 Parity Min",           f"${parity_min:.3f}",                         None),
        ("📈 Parity Max",           f"${parity_max:.3f}",                         None),
        ("🌡️ IV Media",            f"{avg_iv:.1f}%",                             None),
        ("💹 Tasso RF",             f"{rfr*100:.2f}%",                            None),
    ]

    for i, (label, value, delta) in enumerate(metrics):
        with cols[i % 2]:
            st.metric(label=label, value=value, delta=delta,
                      delta_color="inverse" if label.startswith("⚠️") and delta else "normal")


# ---------------------------------------------------------------------------
# Funzione principale pubblica
# ---------------------------------------------------------------------------

def render_parity_tab() -> None:
    """
    Renderizza la scheda Put/Call Parity Analysis completa.
    Chiamare all'interno di un `with tab:` di Streamlit.
    """
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown("## 🔄 Put/Call Parity Analysis")
    st.caption(
        "Rileva deviazioni dalla parità put/call e opportunità di arbitraggio su options S&P/ETF."
    )

    # ------------------------------------------------------------------
    # 1. Controlli di caricamento dati
    # ------------------------------------------------------------------
    st.markdown("---")
    col_t, col_r, col_btn = st.columns([2, 1, 1])
    with col_t:
        ticker_sym = st.selectbox(
            "Ticker",
            ["SPY", "QQQ", "IWM", "AAPL", "TSLA", "NVDA", "AMZN"],
            key="parity_ticker",
        )
    with col_r:
        rfr = (
            st.number_input(
                "Risk-Free Rate %",
                value=4.0,
                min_value=0.0,
                max_value=20.0,
                step=0.25,
                format="%.2f",
                key="parity_rfr",
            )
            / 100.0
        )
    with col_btn:
        st.write("")  # spacer
        load_btn = st.button("📥 Carica Dati", key="parity_load", use_container_width=True)

    # ------------------------------------------------------------------
    # 2. Inizializzazione session state
    # ------------------------------------------------------------------
    for key in ("parity_ready", "parity_spot", "parity_expirations", "parity_sym"):
        if key not in st.session_state:
            st.session_state[key] = None

    if load_btn:
        with st.spinner(f"Connessione a Yahoo Finance per {ticker_sym}…"):
            try:
                spot, expirations = _fetch_spot_and_expirations(ticker_sym)
                st.session_state.update(
                    {
                        "parity_ready": True,
                        "parity_spot": spot,
                        "parity_expirations": expirations,
                        "parity_sym": ticker_sym,
                        "parity_df": None,  # reset cache catene
                    }
                )
                st.success(
                    f"✓ **{ticker_sym}** | Spot: **${spot:,.2f}** | "
                    f"{len(expirations)} scadenze disponibili"
                )
            except Exception as exc:
                st.error(f"Errore nel caricamento: {exc}")
                return

    if not st.session_state.get("parity_ready"):
        st.info("👆 Seleziona un ticker e clicca **Carica Dati** per iniziare.")
        return

    spot: float = st.session_state["parity_spot"]
    expirations: list[str] = st.session_state["parity_expirations"]
    current_sym: str = st.session_state["parity_sym"]

    # ------------------------------------------------------------------
    # 3. Selezione scadenze
    # ------------------------------------------------------------------
    st.markdown("---")
    col_exp, col_apply = st.columns([4, 1])
    with col_exp:
        selected_expiries: list[str] = st.multiselect(
            f"📅 Scadenze disponibili (max {MAX_EXPIRIES})",
            options=expirations,
            default=[expirations[0]] if expirations else [],
            max_selections=MAX_EXPIRIES,
            key="parity_expiries",
        )
    with col_apply:
        st.write("")
        apply_btn = st.button("✅ Applica", key="parity_apply", use_container_width=True)

    if not selected_expiries:
        st.warning("Seleziona almeno una scadenza.")
        return

    # ------------------------------------------------------------------
    # 4. Caricamento catene e calcolo parity
    # ------------------------------------------------------------------
    need_reload = apply_btn or st.session_state.get("parity_df") is None

    if need_reload:
        all_dfs: list[pd.DataFrame] = []
        prog = st.progress(0, text="Caricamento catene opzioni…")
        for i, exp in enumerate(selected_expiries):
            try:
                calls_raw, puts_raw = _fetch_chain(current_sym, exp)
                dte = compute_dte(exp)
                df_exp = build_parity_df(calls_raw, puts_raw, spot, rfr, exp, dte)
                if not df_exp.empty:
                    all_dfs.append(df_exp)
            except Exception as exc:
                st.warning(f"⚠️ {exp}: {exc}")
            prog.progress((i + 1) / len(selected_expiries), text=f"Caricamento {exp}…")
        prog.empty()

        if not all_dfs:
            st.error("Nessun dato valido trovato per le scadenze selezionate.")
            return

        st.session_state["parity_df"] = pd.concat(all_dfs, ignore_index=True)

    full_df: pd.DataFrame = st.session_state["parity_df"]
    if full_df is None or full_df.empty:
        st.warning("Dati non disponibili.")
        return

    # ------------------------------------------------------------------
    # 5. Filtri Strike
    # ------------------------------------------------------------------
    st.markdown("---")
    col_filter, col_slider = st.columns([2, 3])

    with col_filter:
        filter_label = st.radio(
            "🎯 Filtro Strike",
            options=["Tutti", "ITM", "ATM ±50", "OTM"],
            horizontal=True,
            key="parity_filter",
        )

    min_s = float(full_df["strike"].min())
    max_s = float(full_df["strike"].max())

    with col_slider:
        strike_range: tuple[float, float] = st.slider(
            "📏 Range Strike Personalizzato",
            min_value=min_s,
            max_value=max_s,
            value=(min_s, max_s),
            step=5.0,
            format="$%.0f",
            key="parity_strike_range",
        )
        st.caption(f"Range: **${strike_range[0]:,.0f}** → **${strike_range[1]:,.0f}**")

    # Applica filtro tipo
    filter_map = {"Tutti": "all", "ITM": "itm", "ATM ±50": "atm", "OTM": "otm"}
    plot_df = filter_strikes(full_df, spot, filter_map[filter_label])

    # Applica range slider (custom override)
    plot_df = plot_df[
        (plot_df["strike"] >= strike_range[0]) & (plot_df["strike"] <= strike_range[1])
    ]

    if plot_df.empty:
        st.warning("Nessuno strike corrisponde ai filtri applicati.")
        return

    # Subsample per performance
    if len(plot_df) > MAX_POINTS:
        plot_df = plot_df.sample(MAX_POINTS, random_state=42).sort_values("strike")

    # ------------------------------------------------------------------
    # 6. Toggle soglie arbitraggio
    # ------------------------------------------------------------------
    show_arb_lines = st.toggle(
        f"⚠️ Mostra soglie arbitraggio (±${ARBITRAGE_THRESHOLD:.2f})",
        value=True,
        key="parity_arb_toggle",
    )

    # ------------------------------------------------------------------
    # 7. Grafico Scatter
    # ------------------------------------------------------------------
    st.markdown("---")
    fig = _build_parity_chart(plot_df, spot, current_sym, show_arb_lines)
    st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------------
    # 8. Layout a 2 colonne: Alert | Metriche
    # ------------------------------------------------------------------
    st.markdown("---")
    col_alert, col_metrics = st.columns([1, 1], gap="medium")

    with col_alert:
        _render_alert_panel(full_df)

    with col_metrics:
        _render_metrics_panel(full_df, plot_df, spot, rfr, selected_expiries)

    # ------------------------------------------------------------------
    # 9. Export
    # ------------------------------------------------------------------
    st.markdown("---")
    st.markdown("#### 📤 Esporta")
    col_e1, col_e2, col_e3 = st.columns(3)

    today_str = date.today().isoformat()

    with col_e1:
        csv_data = full_df.to_csv(index=False)
        st.download_button(
            label="📥 CSV Dati",
            data=csv_data,
            file_name=f"parity_{current_sym}_{today_str}.csv",
            mime="text/csv",
            key="parity_export_csv",
            use_container_width=True,
        )

    with col_e2:
        try:
            img_bytes = fig.to_image(format="png", width=1400, height=650, scale=2)
            st.download_button(
                label="📸 PNG Grafico",
                data=img_bytes,
                file_name=f"parity_{current_sym}_{today_str}.png",
                mime="image/png",
                key="parity_export_png",
                use_container_width=True,
            )
        except Exception:
            st.button(
                "📸 PNG (installa kaleido)",
                disabled=True,
                key="parity_export_png_disabled",
                use_container_width=True,
                help="Esegui: pip install kaleido",
            )

    with col_e3:
        # URL shareable: encode params nel query string
        params = (
            f"?ticker={current_sym}"
            f"&rfr={rfr*100:.2f}"
            f"&expiries={','.join(selected_expiries)}"
        )
        st.text_input(
            "🔗 URL Shareable",
            value=f"http://localhost:8501/{params}",
            key="parity_share_url",
            help="Copia il link per condividere la configurazione corrente",
        )

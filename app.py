import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import yfinance as yf
from scipy.stats import norm

# --- Funzioni di Supporto ---
def clean_val(val):
    """Pulisce stringhe sporche (%, unch, virgole) e le converte in float."""
    if pd.isna(val): return 0.0
    s = str(val).replace('%', '').replace('unch', '0').replace(',', '').strip()
    try:
        return float(s)
    except:
        return 0.0

def bsm_gamma(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0 or S <= 0: return 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (S * sigma * np.sqrt(T))
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))

def plot_gex(df, spot, title):
    gex_by_strike = df.groupby('Strike')['GEX'].sum().reset_index()
    fig = go.Figure(go.Bar(
        x=gex_by_strike['Strike'],
        y=gex_by_strike['GEX'],
        marker_color=np.where(gex_by_strike['GEX'] >= 0, '#00CC96', '#EF553B')
    ))
    fig.update_layout(
        title=title,
        template="plotly_dark",
        xaxis_title="Strike Price",
        yaxis_title="Total Gamma Exposure ($)",
        xaxis_range=[spot*0.9, spot*1.1]
    )
    fig.add_vline(x=spot, line_dash="dash", line_color="yellow", annotation_text=f"SPOT: {spot:.2f}")
    st.plotly_chart(fig, use_container_width=True)

# --- UI ---
st.set_page_config(page_title="GEX QUANT PRO", layout="wide")
st.title("🛡️ GEX QUANT: Terminale di Analisi")

# Sezione CSV
with st.expander("📂 MODALITÀ CSV: Carica il tuo file", expanded=True):
    uploaded_file = st.file_uploader("Seleziona il file .csv", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        
        # Conversione forzata di tutte le colonne necessarie
        df['Moneyness'] = df['Moneyness'].apply(clean_val)
        df['Gamma'] = df['Gamma'].apply(clean_val)
        df['Open Int'] = df['Open Int'].apply(clean_val)
        df['Strike'] = df['Strike'].apply(clean_val)
        
        # Identificazione SPOT
        try:
            idx_spot = df['Moneyness'].abs().idxmin()
            spot_val = float(df.loc[idx_spot, 'Strike'])
            
            # Calcolo GEX - Qui usiamo float() per sicurezza assoluta
            df['GEX'] = df.apply(lambda r: 
                float(r['Gamma']) * float(r['Open Int']) * 100.0 * spot_val if str(r['Type']).capitalize() == 'Call' 
                else -float(r['Gamma']) * float(r['Open Int']) * 100.0 * spot_val, axis=1)
            
            st.metric("Spot Price Rilevato", f"${spot_val:,.2f}")
            plot_gex(df, spot_val, "Profilo Gamma Exposure (Istituzionale)")
            
        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {e}")

# Sezione Live
with st.expander("🌐 MODALITÀ LIVE: Yahoo Finance"):
    ticker = st.selectbox("Ticker", ["SPY", "QQQ", "IWM"])
    if st.button("Analizza Live"):
        tk = yf.Ticker(ticker)
        spot_live = tk.history(period="1d")['Close'].iloc[-1]
        opts = tk.option_chain(tk.options[0])
        live_df = pd.concat([opts.calls.assign(Type='Call'), opts.puts.assign(Type='Put')])
        live_df = live_df.rename(columns={'strike': 'Strike', 'openInterest': 'Open Int', 'impliedVolatility': 'IV'})
        
        live_df['GEX'] = live_df.apply(lambda r: 
            bsm_gamma(spot_live, r['Strike'], 0.02, 0.04, r['IV']) * r['Open Int'] * 100 * spot_live 
            if r['Type'] == 'Call' else 
            -bsm_gamma(spot_live, r['Strike'], 0.02, 0.04, r['IV']) * r['Open Int'] * 100 * spot_live, axis=1)
        
        plot_gex(live_df, spot_live, f"GEX Live: {ticker}")

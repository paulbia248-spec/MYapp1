import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import yfinance as yf
from scipy.stats import norm

# --- Funzioni di Calcolo ---
def bsm_gamma(S, K, T, r, sigma):
    """Calcola la Gamma teorica."""
    if T <= 0 or sigma <= 0 or S <= 0: return 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))

def plot_gex(df, spot, title):
    """Genera il grafico GEX."""
    gex_by_strike = df.groupby('Strike')['GEX'].sum().reset_index()
    fig = go.Figure(go.Bar(
        x=gex_by_strike['Strike'],
        y=gex_by_strike['GEX'],
        marker_color=np.where(gex_by_strike['GEX'] >= 0, '#00CC96', '#EF553B')
    ))
    fig.update_layout(title=title, template="plotly_dark", xaxis_range=[spot*0.95, spot*1.05])
    st.plotly_chart(fig, use_container_width=True)

# --- UI PRINCIPALE ---
st.set_page_config(page_title="GEX QUANT PRO", layout="wide")
st.title("🛡️ GEX QUANT: Terminale di Analisi")

# 1. MODALITÀ CSV (A SCOMPARSA)
with st.expander("📂 IMPORTA DATI CSV (Istituzionale)", expanded=False):
    uploaded_file = st.file_uploader("Carica il file .csv", type="csv")
    if uploaded_file:
        df_csv = pd.read_csv(uploaded_file)
        
        # FUNZIONE DI PULIZIA AUTOMATICA
        def clean_numeric(column):
            return pd.to_numeric(
                df_csv[column].astype(str)
                .str.replace('%', '', regex=False)
                .str.replace('unch', '0', regex=False)
                .str.replace(',', '', regex=False), # Rimuove eventuali virgole americane
                errors='coerce'
            ).fillna(0)

        # Puliamo le colonne critiche prima di usarle
        df_csv['Moneyness'] = clean_numeric('Moneyness')
        df_csv['Gamma'] = clean_numeric('Gamma')
        df_csv['Open Int'] = clean_numeric('Open Int')
        
        # Ora il calcolo dello SPOT non fallirà più
        try:
            # Troviamo lo strike dove la Moneyness è più vicina a zero
            idx_spot = df_csv['Moneyness'].abs().idxmin()
            spot_csv = df_csv.loc[idx_spot, 'Strike']
            
            st.success(f"Dati caricati correttamente. Spot Price stimato: ${spot_csv}")

            # Calcolo GEX
            df_csv['Type'] = df_csv['Type'].str.capitalize()
            df_csv['GEX'] = df_csv.apply(
                lambda r: r['Gamma'] * r['Open Int'] * 100 * spot_csv if r['Type'] == 'Call' 
                else -r['Gamma'] * r['Open Int'] * 100 * spot_csv, axis=1
            )
            
            # Grafico
            plot_gex(df_csv, spot_csv, "Gamma Exposure dal tuo CSV")
            
        except Exception as e:
            st.error(f"Errore nel calcolo dei dati: {e}")

# 2. MODALITÀ LIVE YAHOO (A SCOMPARSA)
with st.expander("🌐 MODALITÀ LIVE: Yahoo Finance (SPY, QQQ, AAPL)"):
    ticker_sym = st.selectbox("Seleziona Ticker", ["SPY", "QQQ", "AAPL", "MSFT"])
    
    if st.button("Scarica Dati Live"):
        with st.spinner("Interrogando Yahoo Finance..."):
            tk = yf.Ticker(ticker_sym)
            spot_live = tk.history(period="1d")['Close'].iloc[-1]
            expirations = tk.options
            
            # Prendiamo la prima scadenza disponibile per l'anteprima
            opt = tk.option_chain(expirations[0])
            calls, puts = opt.calls, opt.puts
            
            # Preparazione dati live
            calls['Type'] = 'Call'
            puts['Type'] = 'Put'
            data_live = pd.concat([calls, puts])
            data_live = data_live.rename(columns={'strike': 'Strike', 'openInterest': 'Open Int', 'impliedVolatility': 'IV'})
            
            # Calcolo Gamma Teorica (perché non presente in yfinance)
            # T = 7 giorni/365 come stima per la prima scadenza
            data_live['GEX'] = data_live.apply(lambda r: 
                bsm_gamma(spot_live, r['Strike'], 0.02, 0.04, r['IV']) * r['Open Int'] * 100 * spot_live 
                if r['Type'] == 'Call' else 
                -bsm_gamma(spot_live, r['Strike'], 0.02, 0.04, r['IV']) * r['Open Int'] * 100 * spot_live, axis=1)
            
            st.metric(f"Spot {ticker_sym}", f"${spot_live:,.2f}")
            plot_gex(data_live, spot_live, f"GEX Live per {ticker_sym} (Scadenza: {expirations[0]})")

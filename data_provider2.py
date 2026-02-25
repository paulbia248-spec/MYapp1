import yfinance as yf
import pandas as pd

def get_yfinance_data(ticker_symbol):
    """
    Crea l'istanza ticker e scarica i dati come mostrato nel video.
    """
    ticker = yf.Ticker(ticker_symbol)
    
    # Otteniamo il prezzo spot attuale
    spot = ticker.history(period="1d")['Close'].iloc[-1]
    
    # Otteniamo tutte le scadenze disponibili (come al minuto 04:45 del video)
    all_expirations = ticker.options
    
    return ticker, spot, all_expirations

def get_specific_chain(ticker_obj, expiration_date):
    """
    Scarica la catena opzioni per una scadenza specifica.
    """
    opt_chain = ticker_obj.option_chain(expiration_date)
    calls = opt_chain.calls.assign(Type='Call')
    puts = opt_chain.puts.assign(Type='Put')
    return pd.concat([calls, puts])

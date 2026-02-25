import yfinance as yf
import pandas as pd

class YahooFinanceProvider:
    """Classe dedicata al recupero dati opzioni da Yahoo Finance."""
    
    @staticmethod
    def get_ticker_data(symbol):
        """Recupera il prezzo spot e l'oggetto ticker."""
        tk = yf.Ticker(symbol)
        # Recupera l'ultimo prezzo di chiusura
        history = tk.history(period="1d")
        if history.empty:
            return None, None
        spot_price = history['Close'].iloc[-1]
        return tk, spot_price

    @staticmethod
    def get_option_chain(tk, expiration=None):
        """
        Recupera la catena di opzioni per una specifica scadenza.
        Se expiration è None, prende la scadenza più vicina.
        """
        if not expiration:
            # Prende la prima data disponibile (es. 0DTE o 1DTE)
            expiration = tk.options[0]
            
        opt = tk.option_chain(expiration)
        
        # Unifica Call e Put in un unico DataFrame
        calls = opt.calls.assign(Type='Call')
        puts = opt.puts.assign(Type='Put')
        df = pd.concat([calls, puts])
        
        # Rinomina per compatibilità con il tuo motore GEX
        df = df.rename(columns={
            'strike': 'Strike',
            'openInterest': 'Open Int',
            'impliedVolatility': 'IV',
            'lastPrice': 'Latest'
        })
        
        return df, expiration

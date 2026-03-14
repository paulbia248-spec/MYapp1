"""
Costanti per l'analisi Put/Call Parity.
"""

# Soglia in dollari oltre cui si segnala un'opportunità di arbitraggio
ARBITRAGE_THRESHOLD: float = 1.0

# Range in punti-indice intorno allo spot per considerare uno strike ATM
ATM_RANGE: float = 25.0

# Massimo numero di scadenze selezionabili contemporaneamente
MAX_EXPIRIES: int = 10

# Massimo numero di punti visualizzati nel grafico (performance)
MAX_POINTS: int = 1000

# Stops colore gradiente DTE: (dte_giorni, hex_color)
# 0 DTE → rosso, 92+ DTE → ciano-blu
DTE_COLOR_STOPS: list[tuple[int, str]] = [
    (0,  "#FF0000"),   # rosso       – scadenza odierna
    (7,  "#FF6600"),   # arancio scuro
    (14, "#FF9900"),   # arancio
    (30, "#FFFF00"),   # giallo
    (60, "#00FF88"),   # verde
    (92, "#00CCFF"),   # ciano-blu   – scadenza lontana
]

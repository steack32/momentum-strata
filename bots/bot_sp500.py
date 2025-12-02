import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime

# --- SMA 200 Rebound : S&P 500 Bot (Trend Pullback Logic) ---

def get_sp500_tickers():
    try:
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = table[0]
        tickers = df['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers]
    except Exception as e:
        print(f"❌ Erreur liste S&P 500 : {e}")
        # Liste de secours
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "TSLA", "META", "BRK-B", "JPM", "V"]

print(f"--- SMA 200 Rebound : S&P 500 Bot ---")
tickers = get_sp500_tickers()
print(f"Analyse de {len(tickers)} entreprises...")

try:
    print("Téléchargement des données historiques (2 ans pour assurer la SMA 200)...")
    # On prend 2 ans pour être sûr d'avoir assez de data pour la SMA 200 même avec les jours fériés
    data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', progress=False, auto_adjust=False, threads=False)
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}")
    exit(1)

candidates = {}
print("\nRecherche de configurations (Prix > SMA 200 & Proche)...")

for ticker in tickers:
    try:
        # Gestion des données multi-index ou simple
        if ticker not in data or 'Adj Close' not in data[ticker]: continue
        
        adj_close = data[ticker]['Adj Close'].dropna()

        # Il nous faut au moins 205 jours pour calculer la SMA 200 et sa pente
        if len(adj_close) < 205: continue
        
        current_price = adj_close.iloc[-1]
        
        # Filtre de prix minimum (penny stocks évités)
        if current_price < 10: continue

        # Calcul de la SMA 200
        sma_200_series = adj_close.rolling(window=200).mean()
        sma_200 = sma_200_series.iloc[-1]
        sma_200_prev = sma_200_series.iloc[-5] # SMA d'il y a 5 jours pour voir la pente

        if pd.isna(sma_200): continue

        # --- CRITÈRES DE SÉLECTION ---
        
        # 1. Le prix doit être AU-DESSUS de la SMA 200
        if current_price <= sma_200: continue

        # 2. La SMA 200 doit être HAUSSIÈRE (pente positive)
        # On évite d'acheter un couteau qui tombe sous une moyenne baissière
        if sma_200 <= sma_200_prev: continue

        # 3. Calcul de la distance (%)
        # On cherche la plus petite distance positive
        distance_pct = (current_price - sma_200) / sma_200
        
        # On stocke la distance pour le classement
        candidates[ticker] = {
            "distance": distance_pct,
            "sma_200": sma_200,
            "price": current_price
        }

    except Exception:
        continue

if not candidates:
    print("⚠️ Aucun candidat trouvé.")
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/sp500.json", "w") as f: json.dump(final_payload, f)
    exit()

# Tri par distance croissante (du plus proche au plus éloigné de la SMA 200)
# On veut les actions qui "rebondissent" ou "consolident" sur la SMA.
sorted_candidates = sorted(candidates.items(), key=lambda x: x[1]['distance'])

# On garde le Top 5 des plus proches
top_5 = sorted_candidates[:5]

print(f"\n✅ Top 5 identifié (Les plus proches du support SMA 200).")

export_data = {}
try: 
    # Récupération des noms complets
    top_tickers_list = [t[0] for t in top_5]
    tickers_info = yf.Tickers(' '.join(top_tickers_list))
except: tickers_info = None

for ticker, info in top_5:
    dist_display = info['distance'] * 100
    print(f"   -> {ticker} : Prix {info['price']:.2f}$ | SMA200 {info['sma_200']:.2f}$ (+{dist_display:.2f}%)")
    
    full_name = ticker
    history_clean = []
    
    try:
        if tickers_info and ticker in tickers_info.tickers:
            infos_dict = tickers_info.tickers[ticker].info
            full_name = infos_dict.get('shortName', infos_dict.get('longName', ticker))

        # Récupération historique récent pour le graphe
        prices = data[ticker]['Adj Close'].dropna()
        history_series = prices.tail(30).tolist()
        history_clean = [round(x, 2) for x in history_series if not pd.isna(x)]

        # --- STOP LOSS STRATEGIQUE ---
        # Le support est la SMA 200. Si on clôture franchement en dessous, la thèse est invalidée.
        # On place le stop 3% sous la SMA 200 pour laisser respirer le prix (mèche).
        sma_200_val = info['sma_200']
        stop_loss_price = round(sma_200_val * 0.97, 2)
        
        entry_price = round(info['price'], 2)

    except Exception as e:
        print(f"      ⚠️ Erreur data pour {ticker}: {e}")
        stop_loss_price = None
        entry_price = None

    export_data[ticker] = {
        "score": round(info['distance'] * 100, 2), # Le score est la distance en % (plus c'est bas, mieux c'est)
        "name": full_name,
        "history": history_clean,
        "entry_price": entry_price,
        "stop_loss": stop_loss_price,
        "rationale": f"Rebond SMA200 (Support à {round(info['sma_200'], 2)}$)"
    }

final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

try:
    with open("../data/sp500.json", "w") as f:
        json.dump(final_payload, f, allow_nan=True)
    print("\n🚀 Terminé. Sauvegarde réussie (Stratégie SMA 200).")
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}")
    exit(1)
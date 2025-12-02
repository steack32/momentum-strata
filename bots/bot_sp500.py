import yfinance as yf
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime

# --- SMA 200 Rebound : S&P 500 Bot (Robust Version) ---

def get_sp500_tickers():
    try:
        # On utilise un User-Agent pour éviter le blocage de Wikipedia
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        table = pd.read_html(url)
        df = table[0]
        tickers = df['Symbol'].tolist()
        clean_tickers = [t.replace('.', '-') for t in tickers]
        print(f"✅ Liste S&P 500 récupérée via Wikipedia : {len(clean_tickers)} actions.")
        return clean_tickers
    except Exception as e:
        print(f"⚠️ Erreur Wikipedia ({e}). Utilisation de la liste de secours (Top 50).")
        # Liste de secours élargie
        return [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "META", "TSLA", "BRK-B", "LLY", "AVGO",
            "JPM", "V", "TSM", "UNH", "WMT", "MA", "XOM", "PG", "JNJ", "HD",
            "ORCL", "MRK", "COST", "ABBV", "CVX", "CRM", "BAC", "AMD", "PEP", "NFLX",
            "KO", "DIS", "ADBE", "TMO", "WFC", "CSCO", "ACN", "MCD", "INTC", "QCOM"
        ]

print(f"--- SMA 200 Rebound : Analyse S&P 500 ---")
tickers = get_sp500_tickers()

# --- Stats pour comprendre ce qui se passe ---
stats = {
    "total": len(tickers),
    "downloaded": 0,
    "too_short_history": 0,
    "sma_falling": 0,    # Tendance baissière
    "price_too_far": 0,  # Trop loin au-dessus
    "price_too_low": 0,  # Crashé sous la SMA
    "candidates": 0
}

try:
    print("Téléchargement des données (peut prendre 1-2 min)...")
    # On télécharge tout d'un coup
    data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', progress=True, threads=True) 
    # Note: threads=True accélère grandement mais peut parfois bugger sur des PC lents. 
    # Si ça plante, remettre threads=False
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}")
    exit(1)

candidates = {}
print("\n🔍 Filtrage des configurations...")

# Si le download renvoie un MultiIndex (cas normal avec plusieurs tickers)
is_multi = isinstance(data.columns, pd.MultiIndex)

for ticker in tickers:
    try:
        # Extraction de la série de prix
        if is_multi:
            if ticker not in data.columns.levels[0]: continue
            adj_close = data[ticker]['Adj Close'].dropna()
        else:
            # Cas où il n'y a qu'un seul ticker
            adj_close = data['Adj Close'].dropna()

        if len(adj_close) < 205:
            stats["too_short_history"] += 1
            continue
        
        stats["downloaded"] += 1
        current_price = adj_close.iloc[-1]
        
        if current_price < 5: continue # Filtre penny stock

        # Calcul SMA 200
        sma_200_series = adj_close.rolling(window=200).mean()
        sma_200 = sma_200_series.iloc[-1]
        sma_200_prev = sma_200_series.iloc[-5] # Pente sur 5 jours

        if pd.isna(sma_200): continue

        # --- CRITÈRES DE SÉLECTION ---

        # 1. Tendance de fond : La SMA 200 doit monter (ou être plate)
        # On ne veut pas attraper un couteau qui tombe
        if sma_200 < sma_200_prev:
            stats["sma_falling"] += 1
            continue

        # 2. Position du prix :
        # On accepte le prix s'il est au-dessus de la SMA...
        # OU s'il est juste un peu en dessous (max 2% en dessous) pour attraper les mèches
        seuil_bas = sma_200 * 0.98
        seuil_haut = sma_200 * 1.05 # On ne veut pas ceux qui sont déjà partis 5% au dessus

        if current_price < seuil_bas:
            stats["price_too_low"] += 1 # Cassure confirmée à la baisse
            continue
        
        if current_price > seuil_haut:
            stats["price_too_far"] += 1 # Déjà trop haut, le train est passé
            continue

        # Calcul de la distance réelle (%)
        distance_pct = (current_price - sma_200) / sma_200
        
        candidates[ticker] = {
            "distance": distance_pct,
            "sma_200": sma_200,
            "price": current_price
        }
        stats["candidates"] += 1

    except Exception as e:
        continue

# --- RAPPORT DE DEBUG ---
print("\n" + "="*40)
print(f"📊 RAPPORT D'ANALYSE")
print(f"   Actions analysées : {stats['downloaded']} / {stats['total']}")
print(f"   ❌ Tendance baissière (SMA ↘) : {stats['sma_falling']}")
print(f"   ❌ Prix trop haut (> +5% SMA) : {stats['price_too_far']}")
print(f"   ❌ Prix trop bas (< -2% SMA)  : {stats['price_too_low']}")
print(f"   ✅ Candidats retenus         : {stats['candidates']}")
print("="*40 + "\n")

if not candidates:
    print("⚠️ Aucun candidat parfait trouvé cette fois-ci.")
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/sp500.json", "w") as f: json.dump(final_payload, f)
    exit()

# Tri : On privilégie ceux qui sont POSITIFS mais proches de 0.
# On trie par valeur absolue de la distance pour trouver les plus proches, qu'ils soient juste dessus ou juste dessous.
sorted_candidates = sorted(candidates.items(), key=lambda x: abs(x[1]['distance']))

top_5 = sorted_candidates[:5]

export_data = {}
try: 
    top_tickers_list = [t[0] for t in top_5]
    tickers_info = yf.Tickers(' '.join(top_tickers_list))
except: tickers_info = None

print("Top 5 retenu :")
for ticker, info in top_5:
    dist_display = info['distance'] * 100
    # Si distance négative, on affiche en rouge dans le terminal (visuel seulement)
    signe = "+" if dist_display >= 0 else ""
    print(f"   -> {ticker} : {info['price']:.2f}$ (SMA: {info['sma_200']:.2f}$) Diff: {signe}{dist_display:.2f}%")
    
    full_name = ticker
    history_clean = []
    
    try:
        if tickers_info and ticker in tickers_info.tickers:
            infos_dict = tickers_info.tickers[ticker].info
            full_name = infos_dict.get('shortName', infos_dict.get('longName', ticker))

        if is_multi:
            prices = data[ticker]['Adj Close'].dropna()
        else:
            prices = data['Adj Close'].dropna()

        history_series = prices.tail(30).tolist()
        history_clean = [round(x, 2) for x in history_series if not pd.isna(x)]

        # STOP LOSS : Toujours 3% sous la SMA 200, peu importe le prix actuel
        stop_loss_price = round(info['sma_200'] * 0.97, 2)
        entry_price = round(info['price'], 2)

    except Exception:
        stop_loss_price = None
        entry_price = None

    export_data[ticker] = {
        "score": info['distance'] * 100,
        "name": full_name,
        "history": history_clean,
        "entry_price": entry_price,
        "stop_loss": stop_loss_price
    }

final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

try:
    with open("../data/sp500.json", "w") as f:
        json.dump(final_payload, f, allow_nan=True)
    print("\n🚀 Sauvegarde JSON réussie.")
except Exception as e:
    print(f"\n❌ Erreur sauvegarde : {e}")
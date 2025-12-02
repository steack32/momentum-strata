import yfinance as yf
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime

# --- SMA 200 Rebound : S&P 500 Bot (Version Optimisée) ---

def get_sp500_tickers():
    """Récupère la liste des tickers S&P 500 depuis Wikipedia ou une liste de secours."""
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        # Utilisation de pandas pour lire la table HTML
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df['Symbol'].tolist()
        # Nettoyage des tickers (ex: BRK.B -> BRK-B pour Yahoo)
        clean_tickers = [t.replace('.', '-') for t in tickers]
        print(f"✅ Liste S&P 500 récupérée via Wikipedia : {len(clean_tickers)} actions.", flush=True)
        return clean_tickers
    except Exception as e:
        print(f"⚠️ Erreur Wikipedia ({e}). Utilisation de la liste de secours (Top 100).", flush=True)
        # Liste de secours plus large (Top 100 caps approx) pour avoir des résultats même si Wiki échoue
        return [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "META", "TSLA", "BRK-B", "LLY", "AVGO",
            "JPM", "V", "TSM", "UNH", "WMT", "MA", "XOM", "PG", "JNJ", "HD",
            "ORCL", "MRK", "COST", "ABBV", "CVX", "CRM", "BAC", "AMD", "PEP", "NFLX",
            "KO", "DIS", "ADBE", "TMO", "WFC", "CSCO", "ACN", "MCD", "INTC", "QCOM",
            "IBM", "GE", "VZ", "DHR", "NKE", "TXN", "NEE", "PM", "UPS", "RTX",
            "HON", "AMGN", "PFE", "LOW", "CAT", "AXP", "SPGI", "UNP", "GS", "BMY",
            "LMT", "BLK", "UBER", "SYK", "T", "ISRG", "PGR", "ETN", "C", "ELV",
            "TJX", "MDLZ", "VRTX", "BKNG", "ADI", "LRCX", "SCHW", "MMC", "CB", "BSX",
            "REGN", "CI", "PLD", "BDX", "KLAC", "PANW", "FI", "TMUS", "CMCSA", "ADP"
        ]

print(f"--- SMA 200 Rebound : Analyse S&P 500 ---", flush=True)
tickers = get_sp500_tickers()

# --- Stats pour le débogage ---
stats = {
    "total": len(tickers),
    "downloaded": 0,
    "too_short": 0,
    "sma_falling": 0,
    "too_far": 0,    
    "too_low": 0,
    "candidates": 0
}

try:
    print("⏳ Téléchargement des données (2 ans)... Cela peut prendre 1 à 2 minutes...", flush=True)
    # threads=True accélère le processus. group_by='ticker' structure les données par action.
    data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', progress=False, threads=True)
    print("✅ Téléchargement terminé.", flush=True)
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}", flush=True)
    exit(1)

candidates = {}
print(f"\n🔍 Analyse ticker par ticker...", flush=True)

# Vérification si MultiIndex (plusieurs tickers) ou SingleIndex (un seul ticker)
is_multi = isinstance(data.columns, pd.MultiIndex)

for i, ticker in enumerate(tickers, 1):
    
    # Log de progression tous les 50 actions pour GitHub Actions
    if i % 50 == 0:
        print(f"   Traitement {i}/{len(tickers)}...", flush=True)

    try:
        # Extraction propre des données
        if is_multi:
            # Si le ticker n'est pas dans les colonnes (échec download spécifique), on passe
            if ticker not in data.columns.levels[0]: continue
            adj_close = data[ticker]['Adj Close'].dropna()
        else:
            adj_close = data['Adj Close'].dropna()

        # On a besoin d'au moins 205 jours (200 pour SMA + 5 pour la pente)
        if len(adj_close) < 205:
            stats["too_short"] += 1
            continue
        
        stats["downloaded"] += 1
        current_price = adj_close.iloc[-1]
        
        # Filtre anti "Penny Stock" (< 5$)
        if current_price < 5: continue

        # --- CALCULS TECHNIQUES ---
        sma_200_series = adj_close.rolling(window=200).mean()
        sma_200 = sma_200_series.iloc[-1]
        sma_200_prev = sma_200_series.iloc[-5] # SMA d'il y a 5 jours

        if pd.isna(sma_200): continue

        # --- FILTRES STRATÉGIQUES (ÉLARGIS) ---

        # 1. Tendance de fond : La SMA 200 ne doit pas plonger
        # On accepte si c'est plat ou montant.
        if sma_200 < sma_200_prev:
            stats["sma_falling"] += 1
            continue

        # 2. Position du prix (Zone "Boucle d'Or")
        # On cherche des actions proches de la SMA 200.
        # BAS : On accepte jusqu'à -3% sous la SMA (chasse aux stops / mèche basse)
        # HAUT : On accepte jusqu'à +15% au-dessus (marché haussier, on est moins strict)
        
        pct_diff = (current_price - sma_200) / sma_200
        
        if pct_diff < -0.03: # Plus bas que -3%
            stats["too_low"] += 1
            continue
        
        if pct_diff > 0.15: # Plus haut que +15%
            stats["too_far"] += 1
            continue

        # Si on arrive ici, c'est un candidat !
        candidates[ticker] = {
            "distance": pct_diff,
            "sma_200": sma_200,
            "price": current_price
        }
        stats["candidates"] += 1

    except Exception as e:
        # Erreur silencieuse pour ne pas spammer les logs
        continue

# --- RAPPORT FINAL ---
print("\n" + "="*40, flush=True)
print(f"📊 RAPPORT D'ANALYSE FINAL", flush=True)
print(f"   Actions scannées    : {stats['downloaded']} / {stats['total']}", flush=True)
print(f"   ❌ Tendance baissière : {stats['sma_falling']}", flush=True)
print(f"   ❌ Trop loin (> +15%) : {stats['too_far']}", flush=True)
print(f"   ❌ Trop bas (< -3%)   : {stats['too_low']}", flush=True)
print(f"   ✅ CANDIDATS RETENUS  : {stats['candidates']}", flush=True)
print("="*40 + "\n", flush=True)

# Si vide, on sauvegarde un JSON vide mais valide pour ne pas casser le site
if not candidates:
    print("⚠️ Aucun candidat trouvé avec ces critères.", flush=True)
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/sp500.json", "w") as f: json.dump(final_payload, f)
    exit()

# --- SÉLECTION DU TOP 5 ---
# On trie par la distance ABSOLUE la plus petite (les plus proches de la ligne, dessus ou dessous)
sorted_candidates = sorted(candidates.items(), key=lambda x: abs(x[1]['distance']))
top_5 = sorted_candidates[:5]

export_data = {}
try: 
    # Récupération des noms complets pour le Top 5 uniquement (optimisation)
    top_tickers_list = [t[0] for t in top_5]
    tickers_info = yf.Tickers(' '.join(top_tickers_list))
except: tickers_info = None

print("Top 5 retenu :", flush=True)

for ticker, info in top_5:
    dist_pct = info['distance'] * 100
    print(f"   -> {ticker} : {info['price']:.2f}$ (Dist SMA: {dist_pct:+.2f}%)", flush=True)
    
    full_name = ticker
    history_clean = []
    
    try:
        # Récupération Nom
        if tickers_info and ticker in tickers_info.tickers:
            infos_dict = tickers_info.tickers[ticker].info
            full_name = infos_dict.get('shortName', infos_dict.get('longName', ticker))
        
        # Récupération Historique pour le mini-graphique (30 derniers jours)
        if is_multi:
            prices = data[ticker]['Adj Close'].dropna()
        else:
            prices = data['Adj Close'].dropna()
            
        history_series = prices.tail(30).tolist()
        history_clean = [round(x, 2) for x in history_series if not pd.isna(x)]

        # DEFINITION DU STOP LOSS
        # Stratégie : Le stop est placé 3% sous la SMA 200, car c'est notre "plancher".
        # Si la SMA est à 100$, le stop est à 97$.
        sma_val = info['sma_200']
        stop_loss_price = round(sma_val * 0.97, 2)
        
        entry_price = round(info['price'], 2)

    except Exception as e:
        print(f"      Err data {ticker}: {e}", flush=True)
        stop_loss_price = 0
        entry_price = 0

    export_data[ticker] = {
        "score": info['distance'] * 100, # Score = distance en %
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
    print("\n🚀 Sauvegarde JSON réussie.", flush=True)
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}", flush=True)
    exit(1)
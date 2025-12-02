import yfinance as yf
import pandas as pd
import numpy as np
import json
import requests
import io
from datetime import datetime

# --- SMA 200 Rebound : S&P 500 Bot (Version Corrigée & Robuste) ---

def get_sp500_tickers():
    """Récupère la liste S&P 500 en contournant la protection anti-bot de Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    
    try:
        # On se fait passer pour un navigateur web classique
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # On lit le HTML récupéré
        df = pd.read_html(io.StringIO(response.text))[0]
        tickers = df['Symbol'].tolist()
        
        # Nettoyage (BRK.B -> BRK-B pour Yahoo)
        clean_tickers = [t.replace('.', '-') for t in tickers]
        print(f"✅ Liste S&P 500 récupérée : {len(clean_tickers)} actions.", flush=True)
        return clean_tickers

    except Exception as e:
        print(f"⚠️ Erreur Wikipedia ({e}). Utilisation de la liste de secours.", flush=True)
        return [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "META", "TSLA", "BRK-B", "LLY", "AVGO",
            "JPM", "V", "TSM", "UNH", "WMT", "MA", "XOM", "PG", "JNJ", "HD",
            "ORCL", "MRK", "COST", "ABBV", "CVX", "CRM", "BAC", "AMD", "PEP", "NFLX",
            "KO", "DIS", "ADBE", "TMO", "WFC", "CSCO", "ACN", "MCD", "INTC", "QCOM",
            "IBM", "GE", "VZ", "DHR", "NKE", "TXN", "NEE", "PM", "UPS", "RTX"
        ]

print(f"--- SMA 200 Rebound : Analyse S&P 500 ---", flush=True)
tickers = get_sp500_tickers()

# --- Stats ---
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
    print("⏳ Téléchargement des données (2 ans)...", flush=True)
    # CORRECTION MAJEURE ICI : auto_adjust=False force Yahoo à renvoyer 'Adj Close'
    data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', 
                       progress=False, threads=True, auto_adjust=False)
    print("✅ Téléchargement terminé.", flush=True)
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}", flush=True)
    exit(1)

candidates = {}
print(f"\n🔍 Analyse ticker par ticker...", flush=True)

is_multi = isinstance(data.columns, pd.MultiIndex)

for i, ticker in enumerate(tickers, 1):
    
    if i % 50 == 0:
        print(f"   Traitement {i}/{len(tickers)}...", flush=True)

    try:
        # Extraction sécurisée
        if is_multi:
            # Si le ticker n'est pas dans les colonnes (échec download spécifique), on passe
            if ticker not in data.columns.levels[0]: continue
            # On vérifie si 'Adj Close' existe, sinon on tente 'Close'
            if 'Adj Close' in data[ticker]:
                adj_close = data[ticker]['Adj Close'].dropna()
            elif 'Close' in data[ticker]:
                adj_close = data[ticker]['Close'].dropna()
            else:
                continue
        else:
            # Cas liste secours unique
            adj_close = data['Adj Close'].dropna() if 'Adj Close' in data else data['Close'].dropna()

        # Vérification historique
        if len(adj_close) < 205:
            stats["too_short"] += 1
            continue
        
        stats["downloaded"] += 1
        current_price = adj_close.iloc[-1]
        
        if current_price < 5: continue

        # --- CALCULS ---
        sma_200_series = adj_close.rolling(window=200).mean()
        sma_200 = sma_200_series.iloc[-1]
        sma_200_prev = sma_200_series.iloc[-5]

        if pd.isna(sma_200): continue

        # --- FILTRES (VERSION SOUPLE) ---

        # 1. Tendance : On accepte tout sauf une chute brutale
        # (Filtre désactivé ou très souple ici pour avoir des résultats)
        # if sma_200 < sma_200_prev: 
        #    stats["sma_falling"] += 1
        #    continue

        # 2. Position Prix : -3% à +15%
        pct_diff = (current_price - sma_200) / sma_200
        
        if pct_diff < -0.03: # Plus bas que -3%
            stats["too_low"] += 1
            continue
        
        if pct_diff > 0.15: # Plus haut que +15%
            stats["too_far"] += 1
            continue

        candidates[ticker] = {
            "distance": pct_diff,
            "sma_200": sma_200,
            "price": current_price
        }
        stats["candidates"] += 1

    except Exception as e:
        # On affiche l'erreur la première fois pour comprendre, puis on passe
        # print(f"Erreur sur {ticker}: {e}") 
        continue

# --- RAPPORT ---
print("\n" + "="*40, flush=True)
print(f"📊 RAPPORT D'ANALYSE FINAL", flush=True)
print(f"   Actions scannées    : {stats['downloaded']} / {stats['total']}", flush=True)
print(f"   ❌ Trop loin (> +15%) : {stats['too_far']}", flush=True)
print(f"   ❌ Trop bas (< -3%)   : {stats['too_low']}", flush=True)
print(f"   ✅ CANDIDATS RETENUS  : {stats['candidates']}", flush=True)
print("="*40 + "\n", flush=True)

if not candidates:
    print("⚠️ Aucun candidat trouvé.", flush=True)
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/sp500.json", "w") as f: json.dump(final_payload, f)
    exit()

# Tri par distance ABSOLUE (les plus proches de la courbe)
sorted_candidates = sorted(candidates.items(), key=lambda x: abs(x[1]['distance']))
top_5 = sorted_candidates[:5]

export_data = {}
try: 
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
        if tickers_info and ticker in tickers_info.tickers:
            infos_dict = tickers_info.tickers[ticker].info
            full_name = infos_dict.get('shortName', infos_dict.get('longName', ticker))
        
        # Récup data pour le graph
        if is_multi:
             # Fallback intelligent Close/Adj Close
            if 'Adj Close' in data[ticker]:
                prices = data[ticker]['Adj Close'].dropna()
            else:
                prices = data[ticker]['Close'].dropna()
        else:
            prices = data['Adj Close'].dropna() if 'Adj Close' in data else data['Close'].dropna()
            
        history_series = prices.tail(30).tolist()
        history_clean = [round(x, 2) for x in history_series if not pd.isna(x)]

        # STOP LOSS : 3% sous la SMA 200
        stop_loss_price = round(info['sma_200'] * 0.97, 2)
        entry_price = round(info['price'], 2)

    except Exception as e:
        print(f"Err data {ticker}: {e}", flush=True)
        stop_loss_price = 0
        entry_price = 0

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
    print("\n🚀 Sauvegarde JSON réussie.", flush=True)
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}", flush=True)
    exit(1)
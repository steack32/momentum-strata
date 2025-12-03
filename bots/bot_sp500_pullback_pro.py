import yfinance as yf
import pandas as pd
import numpy as np
import json
import requests
import io
import os
from datetime import datetime

# --- SMA 200 Rebound : S&P 500 Bot (Stratégie Pullback) ---

def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        df_sp500 = None
        for df in tables:
            if 'Symbol' in df.columns:
                df_sp500 = df; break
        
        if df_sp500 is None: raise ValueError("Colonne 'Symbol' introuvable.")
        tickers = df_sp500['Symbol'].tolist()
        clean_tickers = [t.replace('.', '-') for t in tickers]
        print(f"✅ Liste S&P 500 complète : {len(clean_tickers)} actions.", flush=True)
        return clean_tickers

    except Exception as e:
        print(f"⚠️ Erreur Wikipedia ({e}). Mode secours activé.", flush=True)
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "META", "TSLA", "BRK-B", "JPM", "V", "XOM"]

print(f"--- PULLBACK BOT : Analyse S&P 500 ---", flush=True)
tickers = get_sp500_tickers()

stats = { "total": len(tickers), "downloaded": 0, "too_short": 0, "too_far": 0, "too_low": 0, "candidates": 0 }

try:
    print(f"⏳ Téléchargement des données (2 ans)...", flush=True)
    data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', progress=False, threads=True, auto_adjust=False)
    print("✅ Téléchargement terminé.", flush=True)
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}", flush=True)
    exit(1)

candidates = {}
print(f"\n🔍 Analyse ticker par ticker...", flush=True)
is_multi = isinstance(data.columns, pd.MultiIndex)

for i, ticker in enumerate(tickers, 1):
    if i % 50 == 0: print(f"   Traitement {i}/{len(tickers)}...", flush=True)
    try:
        if is_multi:
            if ticker not in data.columns.levels[0]: continue
            if 'Adj Close' in data[ticker]: adj_close = data[ticker]['Adj Close'].dropna()
            elif 'Close' in data[ticker]: adj_close = data[ticker]['Close'].dropna()
            else: continue
        else:
            adj_close = data['Adj Close'].dropna() if 'Adj Close' in data else data['Close'].dropna()

        if len(adj_close) < 205: stats["too_short"] += 1; continue
        stats["downloaded"] += 1
        current_price = adj_close.iloc[-1]
        if current_price < 5: continue
        sma_200 = adj_close.rolling(window=200).mean().iloc[-1]
        if pd.isna(sma_200): continue

        pct_diff = (current_price - sma_200) / sma_200
        if pct_diff < -0.03: stats["too_low"] += 1; continue
        if pct_diff > 0.15: stats["too_far"] += 1; continue

        candidates[ticker] = { "distance": pct_diff, "sma_200": sma_200, "price": current_price }
        stats["candidates"] += 1
    except Exception: continue

print("\n" + "="*40 + f"\n📊 RAPPORT PULLBACK\n   ✅ Candidats : {stats['candidates']}\n" + "="*40 + "\n", flush=True)

# Tri par distance ABSOLUE (Top 10 retenu pour Pro)
sorted_candidates = sorted(candidates.items(), key=lambda x: abs(x[1]['distance']))
top_10 = sorted_candidates[:10]

export_data = {}
try: tickers_info = yf.Tickers(' '.join([t[0] for t in top_10]))
except: tickers_info = None

for ticker, info in top_10:
    full_name = ticker
    history_clean = []
    try:
        if tickers_info and ticker in tickers_info.tickers:
            infos_dict = tickers_info.tickers[ticker].info
            full_name = infos_dict.get('shortName', infos_dict.get('longName', ticker))
        if is_multi:
            prices = data[ticker]['Adj Close'].dropna() if 'Adj Close' in data[ticker] else data[ticker]['Close'].dropna()
        else:
            prices = data['Adj Close'].dropna() if 'Adj Close' in data else data['Close'].dropna()   
        history_clean = [round(x, 2) for x in prices.tail(30).tolist() if not pd.isna(x)]
        stop_loss_price = round(info['sma_200'] * 0.97, 2)
        entry_price = round(info['price'], 2)
    except Exception: stop_loss_price = 0; entry_price = 0

    export_data[ticker] = {
        "score": info['distance'] * 100,
        "name": full_name,
        "history": history_clean,
        "entry_price": entry_price,
        "stop_loss": stop_loss_price
    }

# --- SAUVEGARDE (TOP 3 VISIBLE) ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
data_dir = os.path.join(project_root, 'data')
if not os.path.exists(data_dir): os.makedirs(data_dir)

# 1. Version PRO (Tout le Top 10)
payload_pro = { "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": export_data }
with open(os.path.join(data_dir, 'sp500_pullback_pro.json'), "w") as f: json.dump(payload_pro, f, allow_nan=True)

# 2. Version FREE (Top 3 seulement)
items_list = list(export_data.items())
# On prend les 3 premiers (slice :3)
free_selection = dict(items_list[:3])

payload_free = { "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": free_selection }
with open(os.path.join(data_dir, 'sp500_pullback_free.json'), "w") as f: json.dump(payload_free, f, allow_nan=True)

print(f"🚀 Sauvegardes terminées.\n   📂 Public (Top 3) : sp500_pullback_free.json\n   🔒 Privé (Top 10) : sp500_pullback_pro.json")

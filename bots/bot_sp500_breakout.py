import yfinance as yf
import pandas as pd
import numpy as np
import json
import requests
import io
import os
from datetime import datetime

# --- PHOENIX BOT : S&P 500 Breakout Stratégie ---

def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        df_sp500 = None
        for df in tables:
            if 'Symbol' in df.columns:
                df_sp500 = df; break
        if df_sp500 is None: raise ValueError("Tableau introuvable")
        
        tickers = df_sp500['Symbol'].tolist()
        clean_tickers = [t.replace('.', '-') for t in tickers]
        print(f"✅ Liste S&P 500 complète : {len(clean_tickers)} actions.", flush=True)
        return clean_tickers
    except Exception as e:
        print(f"⚠️ Erreur Wikipedia ({e}). Mode secours.", flush=True)
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "TSLA", "AMD", "META"]

print(f"--- PHOENIX BOT : Chasse aux Breakouts SMA 200 ---", flush=True)
tickers = get_sp500_tickers()

stats = {
    "total": len(tickers), "downloaded": 0,
    "no_breakout": 0, "low_volume": 0, "candidates": 0
}

try:
    print(f"⏳ Téléchargement des données (1 an)...", flush=True)
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', 
                       progress=False, threads=True, auto_adjust=False)
    print("✅ Données reçues.", flush=True)
except Exception as e:
    print(f"❌ Erreur critique : {e}", flush=True)
    exit(1)

candidates = {}
print(f"\n🔍 Recherche de cassures avec fort volume...", flush=True)

is_multi = isinstance(data.columns, pd.MultiIndex)

for i, ticker in enumerate(tickers, 1):
    if i % 50 == 0: print(f"   Scan {i}/{len(tickers)}...", flush=True)

    try:
        if is_multi:
            if ticker not in data.columns.levels[0]: continue
            # Récup Prix et Volume
            if 'Adj Close' in data[ticker]: price_series = data[ticker]['Adj Close'].dropna()
            elif 'Close' in data[ticker]: price_series = data[ticker]['Close'].dropna()
            else: continue
            
            if 'Volume' in data[ticker]: vol_series = data[ticker]['Volume'].dropna()
            else: continue
        else:
            price_series = data['Adj Close'].dropna() if 'Adj Close' in data else data['Close'].dropna()
            vol_series = data['Volume'].dropna() if 'Volume' in data else None

        if len(price_series) < 205 or vol_series is None: continue
        stats["downloaded"] += 1

        current_price = price_series.iloc[-1]
        prev_price = price_series.iloc[-2]
        current_vol = vol_series.iloc[-1]
        
        sma_200_series = price_series.rolling(window=200).mean()
        sma_200 = sma_200_series.iloc[-1]
        sma_200_prev = sma_200_series.iloc[-2]

        if pd.isna(sma_200): continue

        # --- FILTRES PHOENIX ---
        
        # 1. Breakout : Prix actuel > SMA et Prix précédent < SMA
        if current_price <= sma_200: 
            stats["no_breakout"] += 1; continue
        if prev_price >= sma_200_prev: 
            stats["no_breakout"] += 1; continue

        # 2. Volume : Doit être explosif (x1.5 moyenne 20 jours)
        avg_vol = vol_series.tail(21).iloc[:-1].mean()
        if avg_vol == 0: continue
        
        vol_ratio = current_vol / avg_vol
        if vol_ratio < 1.5:
            stats["low_volume"] += 1; continue

        candidates[ticker] = {
            "breakout_pct": (current_price - sma_200) / sma_200,
            "vol_ratio": vol_ratio,
            "sma_200": sma_200,
            "price": current_price
        }
        stats["candidates"] += 1
        print(f"   🔥 DÉTECTION : {ticker} (Vol x{vol_ratio:.1f})", flush=True)

    except Exception:
        continue

# --- RAPPORT ---
print("\n" + "="*40, flush=True)
print(f"📊 RAPPORT PHOENIX", flush=True)
print(f"   Scannés       : {stats['downloaded']}", flush=True)
print(f"   🔥 Candidats  : {stats['candidates']}", flush=True)
print("="*40 + "\n", flush=True)

# Tri par puissance du VOLUME
sorted_candidates = sorted(candidates.items(), key=lambda x: x[1]['vol_ratio'], reverse=True)
top_5 = sorted_candidates[:5]

export_data = {}
try: tickers_info = yf.Tickers(' '.join([t[0] for t in top_5]))
except: tickers_info = None

for ticker, info in top_5:
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
        stop_loss_price = round(info['sma_200'] * 0.98, 2) # Stop serré pour breakout
        entry_price = round(info['price'], 2)

    except Exception:
        stop_loss_price = 0; entry_price = 0

    export_data[ticker] = {
        "score": info['breakout_pct'] * 100, 
        "name": f"Vol: x{info['vol_ratio']:.1f} | {full_name}", 
        "history": history_clean,
        "entry_price": entry_price,
        "stop_loss": stop_loss_price
    }

# --- SAUVEGARDE ROBUSTE (CHEMIN ABSOLU) ---
final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": export_data}
script_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(os.path.dirname(script_dir), 'data', 'sp500_breakout.json')

try:
    with open(json_path, "w") as f: json.dump(final_payload, f, allow_nan=True)
    print(f"🚀 Sauvegarde réussie : {json_path}", flush=True)
except Exception as e:
    print(f"❌ Erreur sauvegarde : {e}", flush=True)
    exit(1)
import yfinance as yf
import pandas as pd
import numpy as np
import json
import requests
import io
from datetime import datetime

# --- STRATÉGIE PHOENIX : S&P 500 Breakout Bot ---
# Cible : Actions qui cassent leur SMA 200 à la hausse avec du VOLUME.

def get_sp500_tickers():
    """Récupère la liste S&P 500 (Robuste)."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        
        df_sp500 = None
        for df in tables:
            if 'Symbol' in df.columns:
                df_sp500 = df
                break
        
        if df_sp500 is None: raise ValueError("Tableau introuvable")
        
        tickers = df_sp500['Symbol'].tolist()
        clean_tickers = [t.replace('.', '-') for t in tickers]
        print(f"✅ Liste S&P 500 : {len(clean_tickers)} actions.", flush=True)
        return clean_tickers

    except Exception as e:
        print(f"⚠️ Erreur Wikipedia ({e}). Mode secours.", flush=True)
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "TSLA", "AMD", "META"]

print(f"--- PHOENIX BOT : Chasse aux Breakouts SMA 200 ---", flush=True)
tickers = get_sp500_tickers()

stats = {
    "total": len(tickers),
    "downloaded": 0,
    "no_breakout": 0,
    "low_volume": 0,
    "candidates": 0
}

try:
    print(f"⏳ Téléchargement des données (1 an)...", flush=True)
    # On a besoin du Volume, auto_adjust=False est important
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
        # 1. Récupération Prix (Adj Close) et Volume
        if is_multi:
            if ticker not in data.columns.levels[0]: continue
            
            # Prix
            if 'Adj Close' in data[ticker]: price_series = data[ticker]['Adj Close'].dropna()
            elif 'Close' in data[ticker]: price_series = data[ticker]['Close'].dropna()
            else: continue
            
            # Volume
            if 'Volume' in data[ticker]: vol_series = data[ticker]['Volume'].dropna()
            else: continue
        else:
            price_series = data['Adj Close'].dropna() if 'Adj Close' in data else data['Close'].dropna()
            vol_series = data['Volume'].dropna() if 'Volume' in data else None

        if len(price_series) < 205 or vol_series is None: continue
        stats["downloaded"] += 1

        # Données actuelles et précédentes
        current_price = price_series.iloc[-1]
        prev_price = price_series.iloc[-2]
        
        current_vol = vol_series.iloc[-1]
        
        # Moyenne Mobile 200
        sma_200_series = price_series.rolling(window=200).mean()
        sma_200 = sma_200_series.iloc[-1]
        sma_200_prev = sma_200_series.iloc[-2] # La SMA d'hier

        if pd.isna(sma_200): continue

        # --- CŒUR DE LA STRATÉGIE PHOENIX ---

        # 1. Le BREAKOUT (Crossover)
        # Aujourd'hui le prix est AU-DESSUS de la SMA 200
        if current_price <= sma_200: 
            stats["no_breakout"] += 1
            continue
        
        # Hier (ou avant-hier), le prix était EN-DESSOUS
        # C'est ce qui définit une "cassure" fraiche.
        if prev_price >= sma_200_prev: 
            # Ce n'est pas un breakout, l'action était déjà au dessus.
            stats["no_breakout"] += 1
            continue

        # 2. Le VOLUME (Confirmation institutionnelle)
        # On calcule le volume moyen sur 20 jours
        avg_vol = vol_series.tail(21).iloc[:-1].mean() # Moyenne sans inclure aujourd'hui
        
        # Le volume du jour doit être explosif (> 150% de la moyenne, soit x1.5)
        # On peut être un peu plus souple (x1.2) si le marché est mou, mais x1.5 est le standard pro.
        vol_ratio = current_vol / avg_vol
        
        if vol_ratio < 1.5:
            stats["low_volume"] += 1
            continue

        # BINGO !
        candidates[ticker] = {
            "breakout_pct": (current_price - sma_200) / sma_200, # De combien on a dépassé
            "vol_ratio": vol_ratio,
            "sma_200": sma_200,
            "price": current_price
        }
        stats["candidates"] += 1
        print(f"   🔥 PHOENIX DÉTECTÉ : {ticker} (Vol x{vol_ratio:.1f})", flush=True)

    except Exception:
        continue

# --- RAPPORT ---
print("\n" + "="*40, flush=True)
print(f"📊 RAPPORT PHOENIX", flush=True)
print(f"   Actions scannées      : {stats['downloaded']}", flush=True)
print(f"   💤 Pas de cassure     : {stats['no_breakout']}", flush=True)
print(f"   🔇 Cassure sans volume : {stats['low_volume']}", flush=True)
print(f"   🔥 CANDIDATS VALIDES  : {stats['candidates']}", flush=True)
print("="*40 + "\n", flush=True)

if not candidates:
    print("⚠️ Aucun breakout valide aujourd'hui.", flush=True)
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/sp500.json", "w") as f: json.dump(final_payload, f)
    exit()

# Tri par puissance du VOLUME (plus il y a de volume, plus le signal est fort)
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
        
        # Récupération historique graph
        if is_multi:
            price_series = data[ticker]['Adj Close'].dropna() if 'Adj Close' in data[ticker] else data[ticker]['Close'].dropna()
        else:
            price_series = data['Adj Close'].dropna() if 'Adj Close' in data else data['Close'].dropna()

        history_series = price_series.tail(30).tolist()
        history_clean = [round(x, 2) for x in history_series if not pd.isna(x)]

        # STOP LOSS : Pour un breakout, si on repasse sous la SMA 200, c'est un échec (Bull Trap).
        # On met le stop juste en dessous (-1% ou -2%).
        stop_loss_price = round(info['sma_200'] * 0.98, 2)
        entry_price = round(info['price'], 2)

    except Exception:
        stop_loss_price = 0
        entry_price = 0

    # On utilise le champ "score" pour afficher le ratio de volume dans l'interface existante
    # Hack : L'interface affiche "Dist SMA" pour le score. 
    # Pour que ça ait du sens, on laisse la distance SMA dans le score, 
    # mais le tri a été fait par volume.
    export_data[ticker] = {
        "score": info['breakout_pct'] * 100, 
        "name": f"Vol: x{info['vol_ratio']:.1f} | {full_name}", # On hack le nom pour afficher le volume
        "history": history_clean,
        "entry_price": entry_price,
        "stop_loss": stop_loss_price
    }

final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

try:
    with open("../data/sp500_breakout.json", "w") as f: json.dump(final_payload, f)
    print("\n🚀 Sauvegarde JSON réussie.", flush=True)
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}", flush=True)
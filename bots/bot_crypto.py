import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime

# --- Momentum Strata : S&P 500 Bot V6 (Fixed Stop Loss Logic) ---

def get_sp500_tickers():
    try:
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = table[0]
        tickers = df['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers]
    except Exception as e:
        print(f"❌ Erreur liste S&P 500 : {e}")
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG"]

print(f"--- Momentum Strata : S&P 500 Bot V6 (Fixed Stop) ---")
tickers = get_sp500_tickers()
print(f"Analyse de {len(tickers)} entreprises...")

try:
    print("Téléchargement des données historiques (Mode séquentiel)...")
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=False, auto_adjust=False, threads=False)
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}")
    exit(1)

valid_candidates = {}
print("\nCalculs en cours...")

for ticker in tickers:
    try:
        if ticker not in data or 'Adj Close' not in data[ticker]: continue
        adj_close = data[ticker]['Adj Close'].dropna()

        if len(adj_close) < 200: continue
        current_price = adj_close.iloc[-1]
        
        if current_price < 10: continue

        sma_200 = adj_close.rolling(window=200).mean().iloc[-1]
        if pd.isna(sma_200) or current_price < sma_200: continue

        momentum = (current_price / adj_close.iloc[-126]) - 1
        valid_candidates[ticker] = momentum

    except Exception:
        continue

if not valid_candidates:
    print("⚠️ Aucun candidat trouvé.")
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/sp500.json", "w") as f: json.dump(final_payload, f)
    exit()

ranking = pd.Series(valid_candidates).sort_values(ascending=False)
top_5 = ranking.head(5)

print(f"\n✅ Top 5 identifié. Calcul des zones...")

export_data = {}
try: tickers_info = yf.Tickers(' '.join(top_5.index))
except: tickers_info = None

for ticker, score in top_5.items():
    print(f"   -> {ticker}...")
    full_name = ticker
    history_clean = []
    entry_min = None
    entry_max = None
    stop_loss_price = None

    try:
        if tickers_info and ticker in tickers_info.tickers:
            infos = tickers_info.tickers[ticker].info
            full_name = infos.get('shortName', infos.get('longName', ticker))

        prices = data[ticker]['Adj Close'].dropna()
        current_price = prices.iloc[-1]

        # --- CORRECTION LOGIQUE STOP LOSS & ZONES ---
        if len(prices) > 30:
            daily_returns = prices.pct_change().dropna()
            if len(daily_returns.tail(20)) >= 20:
                # 1. Volatilité
                volatility_pct = daily_returns.tail(20).std()
                
                if not pd.isna(volatility_pct):
                    # Stop Loss Initial = Prix Actuel - (3.0 x Volatilité)
                    stop_dist_pct = volatility_pct * 3.0
                    stop_loss_raw = current_price * (1 - stop_dist_pct)

                    # Zone d'entrée : Prix Actuel jusqu'à -1.5% (plus serré pour actions)
                    entry_max_raw = current_price
                    entry_min_raw = current_price * 0.985

                    # SÉCURITÉ CRITIQUE
                    if stop_loss_raw >= entry_min_raw:
                         stop_loss_raw = entry_min_raw * 0.99

                    stop_loss_price = round(stop_loss_raw, 2)
                    entry_max = round(entry_max_raw, 2)
                    entry_min = round(entry_min_raw, 2)

        history_series = prices.tail(30).tolist()
        history_clean = [round(x, 2) for x in history_series if not pd.isna(x)]

    except Exception as e:
        print(f"      ⚠️ Erreur calculs pour {ticker}: {e}")

    export_data[ticker] = {
        "score": score, "name": full_name, "history": history_clean,
        "entry_min": entry_min, "entry_max": entry_max, "stop_loss": stop_loss_price
    }

final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

try:
    with open("../data/sp500.json", "w") as f:
        json.dump(final_payload, f, allow_nan=True)
    print("\n🚀 Terminé. Sauvegarde réussie (Stop Loss corrigé).")
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}")
    exit(1)
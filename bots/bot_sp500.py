import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime

# --- Momentum Strata : S&P 500 Bot V5 (Trailing Stop Logic) ---

def get_sp500_tickers():
    try:
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = table[0]
        tickers = df['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers]
    except Exception as e:
        print(f"❌ Erreur liste S&P 500 : {e}")
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG"]

print(f"--- Momentum Strata : S&P 500 Bot V5 (Trailing Stop) ---")
tickers = get_sp500_tickers()
print(f"Analyse de {len(tickers)} entreprises...")

try:
    print("Téléchargement des données historiques (Mode séquentiel)...")
    # threads=False pour stabilité GitHub
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

print(f"\n✅ Top 5 identifié. Calcul des Stop Suiveurs...")

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

        # --- NOUVELLE LOGIQUE STOP SUIVEUR (Chandelier Exit) ---
        if len(prices) > 30:
            daily_returns = prices.pct_change().dropna()
            if len(daily_returns.tail(20)) >= 20:
                # 1. Volatilité (écart-type 20 jours)
                volatility_pct = daily_returns.tail(20).std()
                
                # 2. Le plus haut sommet des 20 derniers jours
                highest_recent_close = prices.tail(20).max()
                
                if not pd.isna(volatility_pct) and not pd.isna(highest_recent_close):
                    # 3. Calcul de la distance du stop (3x volatilité)
                    stop_dist_pct = volatility_pct * 3.0
                    
                    # 4. Le stop est placé sous le plus haut récent
                    trailing_stop_raw = highest_recent_close * (1 - stop_dist_pct)

                    # Sécurité : Si le stop théorique est au-dessus du prix actuel (crash récent),
                    # on le ramène juste sous le prix actuel.
                    trailing_stop_raw = min(trailing_stop_raw, current_price * 0.995)
                    
                    stop_loss_price = round(trailing_stop_raw, 2)
                    entry_max = round(current_price, 2)
                    entry_min = round(current_price * 0.985, 2)
                    print(f"      [High 20j: {highest_recent_close:.2f}$] -> Trailing Stop: {stop_loss_price}$")

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
    print("\n🚀 Terminé. Sauvegarde réussie (Stop Suiveur intégré).")
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}")
    exit(1)
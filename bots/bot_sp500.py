import yfinance as yf
import pandas as pd
import json
from datetime import datetime
import numpy as np

# --- FONCTION S&P 500 ---
def get_sp500_tickers():
    try:
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = table[0]
        tickers = df['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers]
    except:
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "META", "LLY", "JPM", "V", "XOM"]

print(f"--- Momentum Strata V5 (Target & Stop) ---")

tickers = get_sp500_tickers()
print(f"Universe : {len(tickers)} actions.")

print("Téléchargement des données...")
try:
    # On a besoin des données journalières pour calculer la volatilité (pas weekly)
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=True, auto_adjust=False, threads=True)
except Exception as e:
    print(f"❌ Erreur critique : {e}")
    exit()

valid_candidates = {}
print("\nAnalyse et Filtrage...")

for ticker in tickers:
    try:
        # Récupération des données
        df_ticker = data[ticker]
        adj_close = df_ticker['Adj Close'].dropna()

        if len(adj_close) < 200: continue

        current_price = adj_close.iloc[-1]
        
        # --- FILTRE 1 : PRIX > 10$ ---
        if current_price < 10: continue

        # --- FILTRE 2 : SMA 200 (Tendance Long terme) ---
        sma_200 = adj_close.rolling(window=200).mean().iloc[-1]
        if current_price < sma_200: continue

        # --- CALCUL MOMENTUM (6 mois ~ 126 jours de bourse) ---
        momentum = (current_price / adj_close.iloc[-126]) - 1
        
        # On stocke le momentum pour le classement
        valid_candidates[ticker] = momentum

    except Exception:
        continue

# CLASSEMENT TOP 5
if not valid_candidates:
    print("⚠️ Aucun candidat.")
    exit()

top_5 = pd.Series(valid_candidates).sort_values(ascending=False).head(5)

# EXPORT DÉTAILLÉ AVEC STOP LOSS ET ZONES
export_data = {}

print(f"\n✅ Top 5 identifié. Calcul des zones d'intervention...")

for ticker, score in top_5.items():
    try:
        # Récupération info
        stock = yf.Ticker(ticker)
        infos = stock.info
        full_name = infos.get('shortName', infos.get('longName', ticker))
        
        # Récupération Série de prix pour ce ticker
        prices = data[ticker]['Adj Close'].dropna()
        current_price = prices.iloc[-1]

        # --- CALCUL TECHNIQUE DU STOP LOSS ---
        # 1. Calculer les rendements quotidiens
        daily_returns = prices.pct_change()
        # 2. Volatilité sur 20 jours (écart-type)
        volatility = daily_returns.tail(20).std()
        
        # STOP LOSS = Prix - (2.5 * Volatilité)
        # C'est un "Volatility Stop" classique
        stop_dist = volatility * 2.5
        stop_loss_price = current_price * (1 - stop_dist)

        # ZONE D'ENTRÉE = Du prix actuel à -1.5%
        entry_max = current_price
        entry_min = current_price * 0.985

        # Historique pour le graph (30 derniers jours)
        history_clean = [round(x, 2) for x in prices.tail(30).tolist()]

        export_data[ticker] = {
            "score": score,
            "name": full_name,
            "history": history_clean,
            "price": round(current_price, 2),
            "stop_loss": round(stop_loss_price, 2),
            "entry_min": round(entry_min, 2),
            "entry_max": round(entry_max, 2)
        }
        print(f"   -> {ticker}: Stop à {round(stop_loss_price, 2)}$")
        
    except Exception as e:
        print(f"Erreur {ticker}: {e}")

final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

with open("data.json", "w") as f:
    json.dump(final_payload, f)

print("\n🚀 Fichier 'data.json' mis à jour avec Stratégie Avancée.")
import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# --- CONFIGURATION ---
tickers = [
    "JPM", "BAC", "XOM", "CVX", "WMT", "PG", "JNJ", "UNH", "HD", "LLY",
    "KO", "PEP", "MRK", "DIS", "MCD", "VZ", "CSCO", "CRM", "NKE", "IBM",
    "GS", "MS", "CAT", "BA", "MMM", "GE", "F", "GM", "UBER", "ABBV"
]

print(f"--- Momentum Strata V3 (Mode Fiable) ---")
print(f"Analyse de {len(tickers)} actifs...")

# --- 1. SCAN RAPIDE (Pour le classement) ---
try:
    # On ne télécharge que le nécessaire pour le classement
    data = yf.download(tickers, period="7mo", progress=False, auto_adjust=False)
    adj_close = data['Adj Close']
    adj_close = adj_close.ffill() # Remplir les trous
except Exception as e:
    print(f"❌ Erreur critique téléchargement global : {e}")
    exit()

# --- 2. CALCUL DU MOMENTUM ---
momentum_scores = adj_close.pct_change(126, fill_method=None).iloc[-1]
momentum_scores = momentum_scores.dropna()

if momentum_scores.empty:
    print("⚠️ Aucune donnée disponible.")
    exit()

# --- 3. SÉLECTION DU TOP 5 ---
ranking = momentum_scores.sort_values(ascending=False)
top_5 = ranking.head(5)

# --- 4. RÉCUPÉRATION DÉTAILLÉE (Un par un pour les graphiques) ---
export_data = {}

print("\n✅ TOP 5 IDENTIFIÉ. Récupération des graphiques un par un...")

for ticker, score in top_5.items():
    print(f"   Traitement de {ticker}...")
    try:
        # A. On utilise l'objet Ticker spécifique (plus fiable pour l'info et l'historique précis)
        stock = yf.Ticker(ticker)
        
        # Récupérer le nom
        # Astuce : Parfois 'shortName' manque, on prend 'longName' ou le ticker
        infos = stock.info
        full_name = infos.get('shortName', infos.get('longName', ticker))
        
        # B. Récupérer l'historique propre pour le Sparkline (1 an, intervalle semaine)
        hist = stock.history(period="1y", interval="1wk")
        
        if hist.empty:
            history_clean = []
        else:
            # On prend les 30 derniers points de clôture
            history_series = hist['Close'].tail(30).tolist()
            # On nettoie (arrondi + suppression des NaN éventuels)
            history_clean = [round(x, 2) for x in history_series if pd.notnull(x)]

        # C. Construction de l'objet
        export_data[ticker] = {
            "score": score,
            "name": full_name,
            "history": history_clean
        }
        
    except Exception as e:
        print(f"   ⚠️ Erreur sur {ticker}: {e}")
        export_data[ticker] = {
            "score": score,
            "name": ticker,
            "history": [100, 100] # Ligne plate par défaut si erreur
        }

# --- 5. EXPORT JSON ---
final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

with open("data.json", "w") as f:
    json.dump(final_payload, f)

print("\n🚀 Fichier 'data.json' mis à jour avec succès.")
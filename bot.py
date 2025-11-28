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

print(f"--- Momentum Strata V2 ---")
print(f"Analyse de {len(tickers)} actifs en cours...")

# --- 1. DONNÉES DE PRIX (MASSIVE) ---
try:
    # On télécharge 1 an pour avoir assez d'historique pour le graphique
    data = yf.download(tickers, period="1y", interval="1wk", progress=False, auto_adjust=False)
    adj_close = data['Adj Close']
    adj_close = adj_close.ffill() # Remplir les trous
except Exception as e:
    print(f"❌ Erreur critique : {e}")
    exit()

# --- 2. CALCUL DU MOMENTUM (Sur les 26 dernières semaines ~ 6 mois) ---
momentum_scores = adj_close.pct_change(26, fill_method=None).iloc[-1]
momentum_scores = momentum_scores.dropna()

# --- 3. SÉLECTION DU TOP 5 ---
if momentum_scores.empty:
    print("⚠️ Aucune donnée.")
    exit()

ranking = momentum_scores.sort_values(ascending=False)
top_5 = ranking.head(5)

# --- 4. ENRICHISSEMENT DES DONNÉES (NOM + GRAPHIQUE) ---
export_data = {}

print("\n✅ TOP 5 GÉNÉRÉ. Récupération des détails...")

for ticker, score in top_5.items():
    try:
        # A. Récupérer le nom complet (Via l'objet Ticker de yfinance)
        stock_info = yf.Ticker(ticker).info
        full_name = stock_info.get('shortName', ticker) # Si pas de nom, on met le ticker
        
        # B. Récupérer l'historique pour le Sparkline (30 derniers points)
        # On prend les prix de clôture de ce ticker spécifique
        history_series = adj_close[ticker].tail(30).tolist()
        # On arrondit pour alléger le JSON
        history_clean = [round(x, 2) for x in history_series]

        # C. Construire l'objet pour ce ticker
        export_data[ticker] = {
            "score": score,
            "name": full_name,
            "history": history_clean
        }
        print(f"   -> {ticker} traité ({full_name})")
        
    except Exception as e:
        print(f"   ⚠️ Erreur sur {ticker}: {e}")
        # Fallback si erreur
        export_data[ticker] = {
            "score": score,
            "name": ticker,
            "history": []
        }

# --- 5. EXPORT JSON ---
final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

with open("data.json", "w") as f:
    json.dump(final_payload, f)

print("\n🚀 Fichier 'data.json' mis à jour avec Noms et Graphiques.")
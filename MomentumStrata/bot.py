import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# --- CONFIGURATION ---
# Liste des actions à analyser (Grandes capitalisations US)
tickers = [
    "JPM", "BAC", "XOM", "CVX", "WMT", "PG", "JNJ", "UNH", "HD", "LLY",
    "KO", "PEP", "MRK", "DIS", "MCD", "VZ", "CSCO", "CRM", "NKE", "IBM",
    "GS", "MS", "CAT", "BA", "MMM", "GE", "F", "GM", "UBER", "ABBV"
]

print(f"--- Démarrage de Momentum Strata ---")
print(f"Analyse de {len(tickers)} actifs du NYSE en cours...")

# --- RÉCUPÉRATION DES DONNÉES ---
try:
    # Téléchargement des données (7 mois pour avoir un historique de 6 mois propre)
    data = yf.download(tickers, period="7mo", progress=False, auto_adjust=False)
    adj_close = data['Adj Close']
    
    # Remplissage des données manquantes (jours fériés/erreurs)
    adj_close = adj_close.ffill()

except Exception as e:
    print(f"❌ Erreur critique : {e}")
    exit()

# --- CALCUL DU MOMENTUM ---
# Calcul de la performance sur 126 jours de bourse (~6 mois)
# fill_method=None évite les avertissements de pandas
momentum_scores = adj_close.pct_change(126, fill_method=None).iloc[-1]

# Suppression des résultats vides (si une action n'a pas assez d'historique)
momentum_scores = momentum_scores.dropna()

# --- SÉLECTION ET TRI ---
if momentum_scores.empty:
    print("⚠️ Aucune donnée disponible.")
else:
    # Tri décroissant et sélection du TOP 5
    ranking = momentum_scores.sort_values(ascending=False)
    top_5 = ranking.head(5)

    # --- AFFICHAGE CONSOLE ---
    print("\n✅ SÉLECTION DE LA SEMAINE (TOP 5) :")
    print("-" * 40)
    for ticker, score in top_5.items():
        print(f"{ticker:<10} | {score:+.2%}")
    print("-" * 40)

    # --- EXPORT VERS JSON (POUR LE SITE WEB) ---
    site_data = {
        "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
        "picks": top_5.to_dict()
    }

    # Création du fichier data.json
    with open("data.json", "w") as f:
        json.dump(site_data, f)

    print("\n🚀 Succès : Fichier 'data.json' mis à jour. Le site est prêt.")
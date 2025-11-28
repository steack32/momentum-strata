import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# --- 1. L'UNIVERS CRYPTO (Top 30 Liquide) ---
# Liste manuelle des principales cryptos (hors stablecoins)
tickers = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", 
    "AVAX-USD", "DOGE-USD", "DOT-USD", "TRX-USD", "LINK-USD", "MATIC-USD",
    "SHIB-USD", "LTC-USD", "BCH-USD", "ATOM-USD", "UNI-USD", "XLM-USD",
    "ETC-USD", "FIL-USD", "HBAR-USD", "ICP-USD", "NEAR-USD", "APT-USD",
    "VET-USD", "MKR-USD", "AAVE-USD", "GRT-USD", "ALGO-USD", "FTM-USD"
]

print(f"--- Momentum Strata : Crypto Bot V2 ---")
print(f"Scan de {len(tickers)} paires face au Dollar...")

# --- 2. TÉLÉCHARGEMENT MASSIF ---
# On télécharge 1 an d'historique journalier
try:
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=True, auto_adjust=False, threads=True)
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}")
    exit()

# --- 3. ANALYSE ET FILTRAGE ---
valid_candidates = {}
print("\nAnalyse des tendances en cours...")

for ticker in tickers:
    try:
        # Récupération des prix de clôture ajustés
        adj_close = data[ticker]['Adj Close'].dropna()

        # Il faut au moins 6 mois de données (~180 jours)
        if len(adj_close) < 180: continue

        current_price = adj_close.iloc[-1]
        
        # --- FILTRE 1 : PRIX MINIMUM ---
        # On ignore les "memecoins" à trop de décimales (< 1 centime) pour éviter les erreurs d'arrondi
        if current_price < 0.01:
            continue

        # --- CALCUL DU MOMENTUM (6 mois ~ 180 jours) ---
        # Formule ROC (Rate of Change)
        momentum = (current_price / adj_close.iloc[-180]) - 1

        valid_candidates[ticker] = momentum

    except Exception:
        continue # On ignore silencieusement les erreurs sur un ticker

# --- 4. CLASSEMENT ---
if not valid_candidates:
    print("⚠️ Aucun candidat trouvé après filtrage.")
    exit()

# Tri décroissant et sélection du Top 5
ranking = pd.Series(valid_candidates).sort_values(ascending=False)
top_5 = ranking.head(5)

print(f"\n✅ Top 5 Crypto identifié. Préparation de l'export...")

# --- 5. RÉCUPÉRATION DÉTAILLÉE (Pour le site) ---
export_data = {}

for ticker, score in top_5.items():
    print(f"   Traitement final : {ticker}...")
    try:
        # Nettoyage du nom (On enlève "-USD" pour l'affichage)
        clean_name = ticker.replace("-USD", "")
        
        # Historique pour le Sparkline (30 derniers jours seulement, plus réactif pour la crypto)
        history_series = data[ticker]['Adj Close'].dropna().tail(30).tolist()
        # On garde 4 décimales pour la précision des petits prix crypto
        history_clean = [round(x, 4) for x in history_series]

        export_data[clean_name] = {
            "score": score,
            "name": f"{clean_name} / US Dollar",
            "history": history_clean,
            # Note: Pas de Stop Loss/Zone d'achat pour l'instant sur ce bot simplifié
            "full_ticker": ticker 
        }
    except:
        export_data[clean_name] = {"score": score, "name": ticker, "history": []}

# --- 6. EXPORT JSON DANS LE DOSSIER DATA ---
final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

# IMPORTANT : On remonte d'un dossier (../) puis on va dans data/
try:
    with open("../data/crypto.json", "w") as f:
        json.dump(final_payload, f)
    print("\n🚀 Terminé. Fichier 'data/crypto.json' mis à jour avec succès.")
except Exception as e:
    print(f"\n❌ Erreur lors de la sauvegarde du JSON : {e}")
    print("Vérifiez que vous lancez bien le script DEPUIS le dossier 'bots/' !")
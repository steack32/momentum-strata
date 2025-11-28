import yfinance as yf
import pandas as pd
import numpy as np # Nécessaire pour gérer les cas limites mathématiques
import json
from datetime import datetime

# --- 1. RÉCUPÉRATION DE LA LISTE S&P 500 ---
def get_sp500_tickers():
    try:
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = table[0]
        tickers = df['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers]
    except Exception as e:
        print(f"❌ Erreur liste S&P 500 : {e}")
        # Liste de secours minimale pour ne pas crash totalement
        return ["AAPL", "MSFT", "NVDA"]

print(f"--- Momentum Strata : S&P 500 Bot V3 (Blindé) ---")
tickers = get_sp500_tickers()
print(f"Analyse de {len(tickers)} entreprises...")

# --- 2. TÉLÉCHARGEMENT MASSIF (Version Stable) ---
try:
    print("Téléchargement (Mode séquentiel pour stabilité)...")
    # MODIFICATION ICI : threads=False pour éviter les crashs sur GitHub Actions
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=False, auto_adjust=False, threads=False)
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}")
    exit()

# --- 3. ANALYSE ET FILTRAGE ---
valid_candidates = {}
print("\nCalculs en cours...")

for ticker in tickers:
    try:
        # Sécurisation de la récupération des données pour un ticker
        if ticker not in data or 'Adj Close' not in data[ticker]:
            continue
            
        adj_close = data[ticker]['Adj Close'].dropna()

        # Filtre : Au moins 200 jours de données pour le SMA200
        if len(adj_close) < 200: continue

        current_price = adj_close.iloc[-1]
        
        # Filtre Prix > 10$
        if current_price < 10: continue

        # Filtre SMA 200
        sma_200 = adj_close.rolling(window=200).mean().iloc[-1]
        # On vérifie que sma_200 n'est pas NaN (Not a Number)
        if pd.isna(sma_200) or current_price < sma_200: continue

        # Calcul Momentum (126 jours)
        momentum = (current_price / adj_close.iloc[-126]) - 1
        valid_candidates[ticker] = momentum

    except Exception:
        continue

# --- 4. CLASSEMENT ---
if not valid_candidates:
    print("⚠️ Aucun candidat trouvé.")
    # On crée un JSON vide pour ne pas casser le site
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/sp500.json", "w") as f: json.dump(final_payload, f)
    exit()

ranking = pd.Series(valid_candidates).sort_values(ascending=False)
top_5 = ranking.head(5)

print(f"\n✅ Top 5 identifié. Calculs détaillés...")

# --- 5. DÉTAILS ET GESTION DU RISQUE ---
export_data = {}

# Tentative de récupération des noms en bloc (peut échouer, ce n'est pas grave)
try: tickers_info = yf.Tickers(' '.join(top_5.index))
except: tickers_info = None

for ticker, score in top_5.items():
    print(f"   -> {ticker}...")
    # Valeurs par défaut en cas d'échec des calculs
    full_name = ticker
    history_clean = []
    entry_min = None
    entry_max = None
    stop_loss_price = None

    try:
        # A. Nom
        if tickers_info and ticker in tickers_info.tickers:
            infos = tickers_info.tickers[ticker].info
            full_name = infos.get('shortName', infos.get('longName', ticker))

        # B. Données de prix
        prices = data[ticker]['Adj Close'].dropna()
        current_price = prices.iloc[-1]

        # C. Calculs Mathématiques Sécurisés
        # On a besoin d'assez de données pour la volatilité (20 jours)
        if len(prices) > 30:
            daily_returns = prices.pct_change().dropna()
            # Sécurité : on vérifie qu'on a bien des rendements sur 20 jours
            if len(daily_returns.tail(20)) >= 20:
                volatility = daily_returns.tail(20).std()
                
                # Si la volatilité est calculable (pas NaN)
                if not pd.isna(volatility):
                    stop_dist = volatility * 2.5
                    stop_loss_raw = current_price * (1 - stop_dist)
                    stop_loss_price = round(stop_loss_raw, 2)
                    
                    entry_max = round(current_price, 2)
                    entry_min = round(current_price * 0.985, 2)

        # D. Historique
        history_series = prices.tail(30).tolist()
        history_clean = [round(x, 2) for x in history_series if not pd.isna(x)]

    except Exception as e:
        print(f"      ⚠️ Erreur calculs pour {ticker} (Utilisation valeurs par défaut): {e}")

    # Construction de l'objet final (avec des valeurs potentiellement nulles si erreur)
    export_data[ticker] = {
        "score": score,
        "name": full_name,
        "history": history_clean,
        "entry_min": entry_min,
        "entry_max": entry_max,
        "stop_loss": stop_loss_price
    }

# --- 6. SAUVEGARDE ---
final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

try:
    with open("../data/sp500.json", "w") as f:
        # allow_nan=True permet au JSON d'accepter des valeurs NaN si elles ont survécu
        json.dump(final_payload, f, allow_nan=True)
    print("\n🚀 Terminé. Sauvegarde réussie.")
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}")
    exit(1) # Force l'erreur dans GitHub Actions pour qu'on le voie
import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# --- 1. RÉCUPÉRATION DE LA LISTE S&P 500 ---
def get_sp500_tickers():
    try:
        # Lecture du tableau des entreprises sur Wikipédia
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = table[0]
        # Récupération des symboles (tickers)
        tickers = df['Symbol'].tolist()
        # Remplacement des points par des tirets pour la compatibilité yfinance (ex: BRK.B -> BRK-B)
        return [t.replace('.', '-') for t in tickers]
    except Exception as e:
        print(f"❌ Erreur lors de la récupération de la liste S&P 500 : {e}")
        # Liste de secours en cas d'erreur
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "META", "LLY", "JPM", "V", "XOM"]

print(f"--- Momentum Strata : S&P 500 Bot (Avec Stop Loss) ---")
tickers = get_sp500_tickers()
print(f"Analyse de {len(tickers)} entreprises du S&P 500...")

# --- 2. TÉLÉCHARGEMENT MASSIF DES DONNÉES ---
# On télécharge 1 an d'historique journalier pour le calcul du momentum, des graphiques et de la volatilité
try:
    print("Téléchargement des données historiques en cours...")
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=True, auto_adjust=False, threads=True)
except Exception as e:
    print(f"❌ Erreur critique lors du téléchargement : {e}")
    exit()

# --- 3. ANALYSE, FILTRAGE ET SÉLECTION ---
valid_candidates = {}
print("\nAnalyse des tendances et calcul du momentum...")

for ticker in tickers:
    try:
        # Récupération des prix de clôture ajustés
        # On a besoin d'au moins 200 jours pour la moyenne mobile (SMA200)
        adj_close = data[ticker]['Adj Close'].dropna()
        if len(adj_close) < 200: continue

        current_price = adj_close.iloc[-1]
        
        # --- FILTRE 1 : PRIX MINIMUM ---
        # On ignore les "penny stocks" pour éviter la volatilité excessive
        if current_price < 10: continue

        # --- FILTRE 2 : TENDANCE (SMA 200) ---
        # On ne garde que les actions au-dessus de leur moyenne mobile 200 jours
        sma_200 = adj_close.rolling(window=200).mean().iloc[-1]
        if current_price < sma_200: continue

        # --- CALCUL DU MOMENTUM (6 mois ~ 126 jours) ---
        # Formule ROC (Rate of Change) : (Prix actuel / Prix il y a 6 mois) - 1
        momentum = (current_price / adj_close.iloc[-126]) - 1

        valid_candidates[ticker] = momentum

    except Exception:
        # On ignore silencieusement les erreurs sur un ticker individuel
        continue

# --- 4. CLASSEMENT DU TOP 5 ---
if not valid_candidates:
    print("⚠️ Aucun candidat trouvé après filtrage.")
    exit()

# Tri décroissant des scores et sélection des 5 meilleurs
ranking = pd.Series(valid_candidates).sort_values(ascending=False)
top_5 = ranking.head(5)

print(f"\n✅ Top 5 S&P 500 identifié. Préparation des données détaillées...")

# --- 5. RÉCUPÉRATION DES DÉTAILS ET EXPORT JSON ---
export_data = {}

# On crée un objet Tickers pour récupérer les infos (noms) en une seule fois si possible
try:
    tickers_info = yf.Tickers(' '.join(top_5.index))
except:
    tickers_info = None

for ticker, score in top_5.items():
    print(f"   Traitement final : {ticker}...")
    try:
        # --- A. Récupération du nom complet ---
        full_name = ticker # Valeur par défaut
        if tickers_info:
            try:
                infos = tickers_info.tickers[ticker].info
                full_name = infos.get('shortName', infos.get('longName', ticker))
            except:
                pass

        # --- B. Récupération des prix pour les calculs ---
        prices = data[ticker]['Adj Close'].dropna()
        current_price = prices.iloc[-1]

        # --- C. Calcul du STOP LOSS (Basé sur la volatilité) ---
        # 1. Calculer les rendements quotidiens
        daily_returns = prices.pct_change()
        # 2. Volatilité sur 20 jours (écart-type des rendements)
        volatility = daily_returns.tail(20).std()
        # 3. Le Stop est placé à 2.5 fois la volatilité quotidienne sous le prix actuel
        stop_dist = volatility * 2.5
        stop_loss_price = current_price * (1 - stop_dist)

        # --- D. Calcul de la ZONE D'ENTRÉE ---
        # Zone idéale : entre le prix actuel et un repli de 1.5%
        entry_max = current_price
        entry_min = current_price * 0.985

        # --- E. Historique pour le graphique Sparkline ---
        # On prend les 30 dernières valeurs et on arrondit
        history_series = prices.tail(30).tolist()
        history_clean = [round(x, 2) for x
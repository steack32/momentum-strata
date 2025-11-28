import yfinance as yf
import pandas as pd
import numpy as np # Nécessaire pour les calculs de volatilité sécurisés
import json
from datetime import datetime

# --- 1. FONCTION POUR RÉCUPÉRER L'UNIVERS CRYPTO LARGE ---
def get_crypto_universe():
    # Liste statique large représentant les principales cryptos liquides (Top ~200 équivalent)
    # Cette méthode est plus stable sur GitHub Actions que d'essayer de scraper des sites tiers.
    tickers = [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD", "DOGE-USD",
        "DOT-USD", "TRX-USD", "LINK-USD", "MATIC-USD", "SHIB-USD", "LTC-USD", "BCH-USD", "ATOM-USD",
        "UNI-USD", "XLM-USD", "ETC-USD", "FIL-USD", "HBAR-USD", "ICP-USD", "NEAR-USD", "APT-USD",
        "VET-USD", "MKR-USD", "AAVE-USD", "GRT-USD", "ALGO-USD", "FTM-USD", "STX-USD", "RNDR-USD",
        "EGLD-USD", "IMX-USD", "INJ-USD", "SAND-USD", "THETA-USD", "AXS-USD", "MANA-USD", "EOS-USD",
        "CAKE-USD", "SNX-USD", "FLOW-USD", "CRV-USD", "KLAY-USD", "XTZ-USD", "NEO-USD", "IOTA-USD",
        "KAVA-USD", "GALA-USD", "CHZ-USD", "MINA-USD", "COMP-USD", "FXS-USD", "ZEC-USD", "RUNE-USD",
        "PAXG-USD", "XEC-USD", "TWT-USD", "DYDX-USD", "1INCH-USD", "BAT-USD", "LDO-USD", "QNT-USD",
        "DASH-USD", "ZIL-USD", "ENJ-USD", "APE-USD", "CVX-USD", "LRC-USD", "ANKR-USD", "KSM-USD",
        "GNO-USD", "BAL-USD", "YFI-USD", "ENS-USD", "BNT-USD", "SUSHI-USD", "HOT-USD", "OMG-USD",
        "ICX-USD", "QTUM-USD", "ONT-USD", "RVN-USD", "GLM-USD", "SC-USD", "IOST-USD", "WAXP-USD",
        "SXP-USD", "LSK-USD", "ZEN-USD", "STORJ-USD", "ALPHA-USD", "BAND-USD", "CKB-USD", "KDA-USD",
        "CELO-USD", "C98-USD", "AUDIO-USD", "FLUX-USD", "HIVE-USD", "UMA-USD", "API3-USD", "SLP-USD",
        "AR-USD", "JASMY-USD", "DAR-USD", "ALICE-USD", "PERP-USD", "SUPER-USD", "TLM-USD"
        # Liste extensible selon besoins
    ]
    return tickers

print(f"--- Momentum Strata : Crypto Bot V4 (Top Large + Stop Loss Wide) ---")
tickers = get_crypto_universe()
print(f"Analyse de {len(tickers)} paires crypto...")

# --- 2. TÉLÉCHARGEMENT MASSIF (Version Stable) ---
try:
    print("Téléchargement des données historiques (Mode séquentiel pour stabilité)...")
    # IMPORTANT : threads=False pour éviter les crashs sur les serveurs GitHub
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=False, auto_adjust=False, threads=False)
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}")
    exit(1)

# --- 3. ANALYSE, FILTRAGE ET SÉLECTION ---
valid_candidates = {}
print("\nCalculs en cours (Momentum & SMA200)...")

for ticker in tickers:
    try:
        # Sécurisation : vérifier si les données existent pour ce ticker
        if ticker not in data or 'Adj Close' not in data[ticker]:
            continue
            
        adj_close = data[ticker]['Adj Close'].dropna()

        # Filtre 1 : Historique suffisant
        # Il faut au moins 200 jours pour la SMA200
        if len(adj_close) < 200: continue

        current_price = adj_close.iloc[-1]
        
        # Filtre 2 : Prix Minimum (Anti-shitcoin)
        # On ignore les prix trop bas (< 0.01$) pour éviter les problèmes d'arrondis
        if current_price < 0.01: continue

        # Filtre 3 : Tendance (SMA 200 jours)
        # Le prix doit être au-dessus de la moyenne mobile 200 jours
        sma_200 = adj_close.rolling(window=200).mean().iloc[-1]
        # Vérification mathématique (éviter les NaN)
        if pd.isna(sma_200) or current_price < sma_200: continue

        # Calcul Momentum (180 jours ~ 6 mois en crypto 24/7)
        momentum = (current_price / adj_close.iloc[-180]) - 1
        valid_candidates[ticker] = momentum

    except Exception:
        # On ignore silencieusement les erreurs individuelles
        continue

# --- 4. CLASSEMENT ---
if not valid_candidates:
    print("⚠️ Aucun candidat trouvé après filtrage.")
    # Sauvegarde d'un JSON vide pour ne pas casser le site
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/crypto.json", "w") as f: json.dump(final_payload, f)
    exit()

# Tri décroissant et sélection du Top 5
ranking = pd.Series(valid_candidates).sort_values(ascending=False)
top_5 = ranking.head(5)

print(f"\n✅ Top 5 Crypto identifié. Calculs détaillés des zones...")

# --- 5. DÉTAILS ET GESTION DU RISQUE ---
export_data = {}

# Tentative de récupération des noms complets (moins fiable sur crypto)
try: tickers_info = yf.Tickers(' '.join(top_5.index))
except: tickers_info = None

for ticker, score in top_5.items():
    print(f"   -> {ticker}...")
    
    # --- Valeurs par défaut en cas d'échec des calculs ---
    clean_name = ticker.replace("-USD", "")
    full_name = f"{clean_name} / US Dollar"
    history_clean = []
    entry_min = None
    entry_max = None
    stop_loss_price = None
    decimals = 2 # Par défaut 2 décimales

    try:
        # A. Tentative de récupération du nom
        if tickers_info and ticker in tickers_info.tickers:
            try:
                infos = tickers_info.tickers[ticker].info
                name = infos.get('shortName', infos.get('longName', clean_name))
                full_name = f"{name} / USD"
            except: pass

        # B. Données de prix pour les calculs
        prices = data[ticker]['Adj Close'].dropna()
        current_price = prices.iloc[-1]
        
        # DÉTERMINATION DES DÉCIMALES INTELLIGENTE
        # Si prix > 10$, on arrondit à 2 décimales (ex: SOL à 150.25$)
        # Si prix < 10$, on arrondit à 4 décimales pour la précision (ex: ADA à 0.4523$)
        decimals = 2 if current_price > 10 else 4

        # C. Calculs Mathématiques Sécurisés (Stop Loss & Zones)
        # On a besoin d'assez de données pour la volatilité (20 jours)
        if len(prices) > 30:
            daily_returns = prices.pct_change().dropna()
            # Sécurité : on vérifie qu'on a bien au moins 20 jours de rendements
            if len(daily_returns.tail(20)) >= 20:
                volatility = daily_returns.tail(20).std()
                
                if not pd.isna(volatility):
                    # --- CONFIGURATION STOP LOSS ---
                    # Multiplicateur plus large pour la crypto : 3.0 x Volatilité
                    stop_multiplier = 3.0 
                    stop_dist = volatility * stop_multiplier
                    stop_loss_raw = current_price * (1 - stop_dist)
                    
                    # --- CONFIGURATION ZONE D'ENTRÉE ---
                    # Zone entre le prix actuel et un repli de 2.5%
                    entry_pullback = 0.025
                    entry_min_raw = current_price * (1 - entry_pullback)

                    # Application des arrondis
                    stop_loss_price = round(stop_loss_raw, decimals)
                    entry_max = round(current_price, decimals)
                    entry_min = round(entry_min_raw, decimals)
                    
                    print(f"      [Volatilité: {volatility:.2%}] -> Stop: {stop_loss_price}$ / Zone: {entry_min}-{entry_max}$")

        # D. Historique (Sparkline, 30 derniers jours)
        history_series = prices.tail(30).tolist()
        history_clean = [round(x, decimals) for x in history_series if not pd.isna(x)]

    except Exception as e:
        print(f"      ⚠️ Erreur calculs pour {ticker} (Utilisation valeurs par défaut): {e}")

    # Construction de l'objet final
    export_data[clean_name] = {
        "score": score,
        "name": full_name,
        "history": history_clean,
        "entry_min": entry_min,
        "entry_max": entry_max,
        "stop_loss": stop_loss_price,
        "full_ticker": ticker, # Nécessaire pour le lien TradingView
        "decimals": decimals # Utile si on veut ajuster l'affichage JS plus tard
    }

# --- 6. SAUVEGARDE ---
final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

try:
    # Sauvegarde dans le dossier parent data/
    with open("../data/crypto.json", "w") as f:
        # allow_nan=True pour éviter les crashs si un calcul mathématique a échoué
        json.dump(final_payload, f, allow_nan=True)
    print(f"\n🚀 Terminé. Fichier 'data/crypto.json' mis à jour avec succès.")
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}")
    exit(1)
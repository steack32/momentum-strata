import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime

# --- Momentum Strata : Crypto Bot V9 (Volatility Filter + Safety Ceiling) ---
# NOUVEAUTÉ V9 : On filtre les actifs trop volatils AVANT de choisir le Top 5.

def get_crypto_universe():
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
    ]
    return tickers

print(f"--- Momentum Strata : Crypto Bot V9 (High Volatility Filter) ---")
tickers = get_crypto_universe()
print(f"Analyse de {len(tickers)} paires crypto...")

try:
    print("Téléchargement des données historiques (Mode séquentiel)...")
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=False, auto_adjust=False, threads=False)
except Exception as e:
    print(f"❌ Erreur critique téléchargement : {e}")
    exit(1)

# --- ÉTAPE INTERMÉDIAIRE : Collecte des données pour filtrage ---
candidates_data = {}
print("\nPré-analyse : Calcul Momentum et Volatilité pour tous...")

for ticker in tickers:
    try:
        if ticker not in data or 'Adj Close' not in data[ticker]: continue
        adj_close = data[ticker]['Adj Close'].dropna()

        # Filtres de base (Historique, Prix min, SMA200)
        if len(adj_close) < 200: continue
        current_price = adj_close.iloc[-1]
        if current_price < 0.01: continue
        sma_200 = adj_close.rolling(window=200).mean().iloc[-1]
        if pd.isna(sma_200) or current_price < sma_200: continue

        # Calcul Momentum
        momentum = (current_price / adj_close.iloc[-180]) - 1
        
        # Calcul Volatilité (nécessaire maintenant pour le filtrage)
        daily_returns = adj_close.pct_change().dropna()
        volatility = np.nan
        if len(daily_returns.tail(20)) >= 20:
            volatility = daily_returns.tail(20).std()

        # On stocke tout si la volatilité est calculable
        if not pd.isna(volatility):
            candidates_data[ticker] = {
                'momentum': momentum,
                'volatility': volatility
            }

    except Exception:
        continue

if not candidates_data:
    print("⚠️ Aucun candidat éligible trouvé.")
    exit_with_empty_json()

# --- ÉTAPE DE FILTRAGE : Suppression de la volatilité extrême ---
df_candidates = pd.DataFrame.from_dict(candidates_data, orient='index')

# On définit le seuil : on exclut le top 20% des plus volatils (Percentile 80)
volatility_threshold = df_candidates['volatility'].quantile(0.80)
print(f"\nSeuil de volatilité (Top 20% exclus) : > {volatility_threshold:.2%}")

# Filtrage
filtered_df = df_candidates[df_candidates['volatility'] <= volatility_threshold].copy()
removed_count = len(df_candidates) - len(filtered_df)
print(f"-> {removed_count} actifs supprimés car trop volatils.")

# --- CLASSEMENT FINAL ---
# Tri des survivants par momentum décroissant
top_5_df = filtered_df.sort_values(by='momentum', ascending=False).head(5)
print(f"\n✅ Top 5 Momentum (Filtré) identifié. Calcul des zones...")

# --- DÉTAILS ET EXPORT ---
export_data = {}
try: tickers_info = yf.Tickers(' '.join(top_5_df.index))
except: tickers_info = None

for ticker, row in top_5_df.iterrows():
    score = row['momentum']
    volatility_pct = row['volatility'] # On récupère la vol déjà calculée
    
    print(f"   -> {ticker} (Vol: {volatility_pct:.2%})...")
    clean_name = ticker.replace("-USD", "")
    full_name = f"{clean_name} / US Dollar"
    history_clean = []
    entry_min = None
    entry_max = None
    stop_loss_price = None
    decimals = 2

    try:
        if tickers_info and ticker in tickers_info.tickers:
            try:
                infos = tickers_info.tickers[ticker].info
                name = infos.get('shortName', infos.get('longName', clean_name))
                full_name = f"{name} / USD"
            except: pass

        prices = data[ticker]['Adj Close'].dropna()
        current_price = prices.iloc[-1]
        decimals = 2 if current_price > 10 else 4

        # --- CALCULS ZONES & STOP (Logique V8 avec Plafond 5%) ---
        highest_recent_close = prices.tail(20).max()
        
        if not pd.isna(highest_recent_close):
            entry_max_raw = current_price
            entry_min_raw = current_price * 0.98

            # Stop théorique large (3x)
            stop_dist_pct = volatility_pct * 3.0
            trailing_stop_raw = highest_recent_close * (1 - stop_dist_pct)

            # Plafond de sécurité V8 (Coussin de 5%)
            safety_ceiling = entry_min_raw * 0.95
            
            final_stop_raw = min(trailing_stop_raw, safety_ceiling)

            stop_loss_price = round(final_stop_raw, decimals)
            entry_max = round(entry_max_raw, decimals)
            entry_min = round(entry_min_raw, decimals)

        history_series = prices.tail(30).tolist()
        history_clean = [round(x, decimals) for x in history_series if not pd.isna(x)]

    except Exception as e:
        print(f"      ⚠️ Erreur calculs pour {ticker}: {e}")

    export_data[clean_name] = {
        "score": score, "name": full_name, "history": history_clean,
        "entry_min": entry_min, "entry_max": entry_max, "stop_loss": stop_loss_price,
        "full_ticker": ticker, "decimals": decimals
    }

# --- SAUVEGARDE ---
def exit_with_empty_json():
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/crypto.json", "w") as f: json.dump(final_payload, f)
    exit()

if not export_data:
     exit_with_empty_json()

final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

try:
    with open("../data/crypto.json", "w") as f:
        json.dump(final_payload, f, allow_nan=True)
    print(f"\n🚀 Terminé. Sauvegarde réussie (Bot V9 - Filtré).")
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}")
    exit(1)
import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime

# --- Momentum Strata : Crypto Bot V8 (Wider Safety Ceiling for Volatility) ---

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

print(f"--- Momentum Strata : Crypto Bot V8 (Wider Safety Ceiling) ---")
tickers = get_crypto_universe()
print(f"Analyse de {len(tickers)} paires crypto...")

try:
    print("Téléchargement des données historiques (Mode séquentiel)...")
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
        
        if current_price < 0.01: continue

        sma_200 = adj_close.rolling(window=200).mean().iloc[-1]
        if pd.isna(sma_200) or current_price < sma_200: continue

        momentum = (current_price / adj_close.iloc[-180]) - 1
        valid_candidates[ticker] = momentum

    except Exception:
        continue

if not valid_candidates:
    print("⚠️ Aucun candidat trouvé.")
    final_payload = {"date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"), "picks": {}}
    with open("../data/crypto.json", "w") as f: json.dump(final_payload, f)
    exit()

ranking = pd.Series(valid_candidates).sort_values(ascending=False)
top_5 = ranking.head(5)

print(f"\n✅ Top 5 Crypto identifié. Calcul des zones...")

export_data = {}
try: tickers_info = yf.Tickers(' '.join(top_5.index))
except: tickers_info = None

for ticker, score in top_5.items():
    print(f"   -> {ticker}...")
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

        # --- LOGIQUE STOP LOSS BLINDÉE (Version large pour Crypto) ---
        if len(prices) > 30:
            daily_returns = prices.pct_change().dropna()
            if len(daily_returns.tail(20)) >= 20:
                volatility_pct = daily_returns.tail(20).std()
                highest_recent_close = prices.tail(20).max()
                
                if not pd.isna(volatility_pct) and not pd.isna(highest_recent_close):
                    # 1. Calcul des zones brutes
                    entry_max_raw = current_price
                    # Zone d'entrée : repli jusqu'à 2%
                    entry_min_raw = current_price * 0.98

                    # 2. Calcul du Stop Suiveur théorique (basé sur les plus hauts)
                    stop_dist_pct = volatility_pct * 3.0 # Stop large 3x
                    trailing_stop_raw = highest_recent_close * (1 - stop_dist_pct)

                    # 3. LE PLAFOND DE SÉCURITÉ (CORRIGÉ POUR CRYPTO)
                    # Le stop ne peut JAMAIS être supérieur à "Prix d'achat minimum - 5%"
                    # Cela laisse un coussin de sécurité de 5% sous la zone d'achat pour absorber la volatilité.
                    safety_ceiling = entry_min_raw * 0.95 
                    
                    # On prend la valeur la plus basse entre le calcul théorique et le plafond de sécurité.
                    final_stop_raw = min(trailing_stop_raw, safety_ceiling)

                    # 4. Arrondis finaux
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

final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

try:
    with open("../data/crypto.json", "w") as f:
        json.dump(final_payload, f, allow_nan=True)
    print(f"\n🚀 Terminé. Sauvegarde réussie (Stop Loss avec marge de 5%).")
except Exception as e:
    print(f"\n❌ Erreur sauvegarde JSON : {e}")
    exit(1)
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import time
import requests
import re

# --- CONFIGURATION ---
# Liste des stablecoins à ignorer (inutiles pour le momentum)
STABLECOINS = ["USDT", "USDC", "DAI", "FDUSD", "TUSA", "USDD", "PYUSD", "USDP", "EURI", "USDE"]

def get_top_cryptos(limit=150):
    """
    Récupère le Top 150 crypto via l'API CoinGecko automatiquement.
    """
    print(f"🔄 Connexion à CoinGecko (Top {limit})...")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": "false"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status() # Lève une erreur si le code n'est pas 200
        data = response.json()
        
        tickers = []
        for coin in data:
            symbol = coin['symbol'].upper()
            
            # On ignore les stablecoins
            if symbol in STABLECOINS:
                continue
                
            # On formate pour Yahoo Finance (ex: BTC -> BTC-USD)
            tickers.append(f"{symbol}-USD")
            
        print(f"✅ {len(tickers)} cryptos récupérées (Stablecoins filtrés).")
        return tickers

    except Exception as e:
        print(f"⚠️ Erreur CoinGecko ({e}). Passage à la liste de secours.")
        # Liste de secours manuelle si l'API échoue
        return [
            "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", 
            "AVAX-USD", "DOGE-USD", "DOT-USD", "LINK-USD", "MATIC-USD", "SHIB-USD",
            "LTC-USD", "UNI7083-USD", "ATOM-USD", "NEAR-USD", "PEPE24478-USD",
            "FET-USD", "RNDR-USD", "INJ-USD", "APT21794-USD", "IMX-USD"
        ]

def analyze_market():
    # 1. Récupération dynamique
    TICKERS = get_top_cryptos(150)
    
    pullback_picks = {}
    breakout_picks = {}
    
    print(f"🚀 Analyse technique lancée sur {len(TICKERS)} actifs...")
    
    analyzed_count = 0
    error_count = 0

    for ticker in TICKERS:
        try:
            # Téléchargement des données (1 an pour avoir une SMA200 valide)
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            
            if df.empty or len(df) < 200:
                continue

            # Nettoyage MultiIndex (spécifique à yfinance récent)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # --- INDICATEURS ---
            df['SMA_200'] = ta.sma(df['Close'], length=200)
            df['SMA_50']  = ta.sma(df['Close'], length=50)
            df['RSI']     = ta.rsi(df['Close'], length=14)
            df['Vol_Avg'] = ta.sma(df['Volume'], length=20)

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            price = curr['Close']
            sma200 = curr['SMA_200']
            
            # Sécurité données
            if pd.isna(sma200) or pd.isna(price) or price <= 0: continue

            # Nettoyage du nom pour l'affichage (enlève -USD et les chiffres bizarres)
            clean_name = ticker.replace('-USD', '')
            clean_name = re.sub(r'\d+', '', clean_name) # Enlève les chiffres (ex: PEPE24478 -> PEPE)

            # --- STRATÉGIE 1 : PHOENIX (BREAKOUT) ---
            # Volume > 1.5x moyenne
            vol_ratio = curr['Volume'] / curr['Vol_Avg'] if (curr['Vol_Avg'] > 0) else 0
            
            # Conditions : Prix > SMA200 ET Bougie Verte ET Volume Explosif
            if (price > sma200) and (price > prev['Close']) and (vol_ratio > 1.5):
                score = ((price - sma200) / sma200) * 100
                stop_loss = min(prev['Low'], price * 0.90) # Stop large (-10%)

                breakout_picks[ticker] = {
                    "name": clean_name,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "vol_ratio": round(vol_ratio, 1),
                    "history": df['Close'].tail(30).values.tolist()
                }

            # --- STRATÉGIE 2 : PULLBACK (REBOND) ---
            dist_sma50 = (price - curr['SMA_50']) / curr['SMA_50']
            
            # Conditions : Prix > SMA200 ET RSI < 55 ET Proche SMA50 (+/- 4%)
            if (price > sma200) and (curr['RSI'] < 55) and (abs(dist_sma50) < 0.04):
                score = ((price - sma200) / sma200) * 100
                stop_loss = curr['SMA_50'] * 0.95 # Stop serré (-5% sous la SMA50)

                pullback_picks[ticker] = {
                    "name": clean_name,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "history": df['Close'].tail(30).values.tolist()
                }
            
            analyzed_count += 1
            
        except Exception as e:
            error_count += 1
            continue

    print(f"✅ Analyse terminée. {analyzed_count} actifs traités.")

    # --- TRI ---
    # Breakout : Trié par volume ratio décroissant
    breakout_sorted = dict(sorted(breakout_picks.items(), key=lambda x: x[1]['vol_ratio'], reverse=True))
    
    # Pullback : Trié par score (distance à la SMA200) décroissant
    pullback_sorted = dict(sorted(pullback_picks.items(), key=lambda x: x[1]['score'], reverse=True))

    return pullback_sorted, breakout_sorted

# --- EXÉCUTION & SAUVEGARDE ---
if __name__ == "__main__":
    pullback_data, breakout_data = analyze_market()

    today = pd.Timestamp.now().strftime("%d/%m/%Y")

    final_pullback = {"date_mise_a_jour": today, "picks": pullback_data}
    final_breakout = {"date_mise_a_jour": today, "picks": breakout_data}

    # Sauvegarde des fichiers PRO
    with open("data/crypto_pullback_pro.json", "w") as f:
        json.dump(final_pullback, f, indent=4)

    with open("data/crypto_breakout_pro.json", "w") as f:
        json.dump(final_breakout, f, indent=4)

    print("💾 Fichiers JSON Crypto sauvegardés avec succès.")
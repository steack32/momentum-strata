import yfinance as yf
import pandas as pd
import json
import time
import requests
import re

# --- CONFIGURATION ---
STABLECOINS = ["USDT", "USDC", "DAI", "FDUSD", "TUSA", "USDD", "PYUSD", "USDP", "EURI", "USDE"]

# --- FONCTIONS TECHNIQUES (REMPLACEMENT PANDAS_TA) ---
def calculate_sma(series, window):
    return series.rolling(window=window).mean()

def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_top_cryptos(limit=150):
    print(f"🔄 Connexion à CoinGecko (Top {limit})...")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": limit, "page": 1, "sparkline": "false"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        tickers = []
        for coin in data:
            symbol = coin['symbol'].upper()
            if symbol in STABLECOINS: continue
            tickers.append(f"{symbol}-USD")
        return tickers
    except Exception:
        print(f"⚠️ Erreur API. Liste de secours.")
        return ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "AVAX-USD", "DOGE-USD", "PEPE24478-USD"]

def analyze_market():
    TICKERS = get_top_cryptos(150)
    pullback_picks = {}
    breakout_picks = {}
    
    print(f"🚀 Analyse Crypto Pro (Native) sur {len(TICKERS)} actifs...")

    for ticker in TICKERS:
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            
            if len(df) < 200: continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # --- CALCULS NATIFS ---
            df['SMA_200'] = calculate_sma(df['Close'], 200)
            df['SMA_50']  = calculate_sma(df['Close'], 50)
            df['RSI']     = calculate_rsi(df['Close'], 14)
            df['Vol_Avg'] = calculate_sma(df['Volume'], 20)

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            price = curr['Close']
            sma200 = curr['SMA_200']
            
            if pd.isna(sma200) or pd.isna(price) or price <= 0: continue

            clean_name = ticker.replace('-USD', '')
            clean_name = re.sub(r'\d+', '', clean_name)

            # STRATÉGIE 1 : BREAKOUT
            vol_ratio = curr['Volume'] / curr['Vol_Avg'] if (curr['Vol_Avg'] > 0) else 0
            if (price > sma200) and (price > prev['Close']) and (vol_ratio > 1.5):
                score = ((price - sma200) / sma200) * 100
                stop_loss = min(prev['Low'], price * 0.90)
                breakout_picks[ticker] = {
                    "name": clean_name,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "vol_ratio": round(vol_ratio, 1),
                    "history": df['Close'].tail(30).values.tolist()
                }

            # STRATÉGIE 2 : PULLBACK
            dist_sma50 = (price - curr['SMA_50']) / curr['SMA_50']
            if (price > sma200) and (curr['RSI'] < 55) and (abs(dist_sma50) < 0.04):
                score = ((price - sma200) / sma200) * 100
                stop_loss = curr['SMA_50'] * 0.95
                pullback_picks[ticker] = {
                    "name": clean_name,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "history": df['Close'].tail(30).values.tolist()
                }
            
        except Exception:
            continue

    breakout_sorted = dict(sorted(breakout_picks.items(), key=lambda x: x[1]['vol_ratio'], reverse=True))
    pullback_sorted = dict(sorted(pullback_picks.items(), key=lambda x: x[1]['score'], reverse=True))
    return pullback_sorted, breakout_sorted

if __name__ == "__main__":
    pullback_data, breakout_data = analyze_market()
    today = pd.Timestamp.now().strftime("%d/%m/%Y")
    
    with open("data/crypto_pullback_pro.json", "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": pullback_data}, f, indent=4)
    with open("data/crypto_breakout_pro.json", "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": breakout_data}, f, indent=4)
        
    print("💾 Fichiers Crypto sauvegardés.")
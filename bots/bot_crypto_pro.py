import yfinance as yf
import pandas as pd
import json
import time
import requests
import re

# --- CONFIGURATION ---
STABLECOINS = ["USDT", "USDC", "DAI", "FDUSD", "TUSA", "USDD", "PYUSD", "USDP", "EURI", "USDE", "BUSD"]

# --- FONCTIONS TECHNIQUES NATIVES (Optimisées) ---
def calculate_sma(series, window):
    return series.rolling(window=window).mean()

def calculate_ema(series, window):
    # Moyenne Mobile Exponentielle (Réagit plus vite aux prix récents)
    return series.ewm(span=window, adjust=False).mean()

def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_top_cryptos(limit=150):
    print(f"🔄 Connexion à CoinGecko (Top {limit})...")
    # On demande un peu plus (200) pour avoir de la marge après filtrage stablecoins
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 200, "page": 1, "sparkline": "false"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        tickers = []
        for coin in data:
            symbol = coin['symbol'].upper()
            if symbol in STABLECOINS: continue
            # On ignore les versions "wrapped" ou peggés bizarres (stETH, WETH, WBTC)
            if symbol.startswith("W") and symbol[1:] in ["BTC", "ETH", "BNB"]: continue
            if "STETH" in symbol: continue
            
            tickers.append(f"{symbol}-USD")
        
        # On garde les 'limit' premiers après filtrage
        return tickers[:limit]
    except Exception:
        print(f"⚠️ Erreur API. Liste de secours.")
        return ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "AVAX-USD", "DOGE-USD", "PEPE24478-USD", "RNDR-USD", "FET-USD", "INJ-USD", "NEAR-USD"]

def analyze_market():
    TICKERS = get_top_cryptos(150)
    pullback_picks = {}
    breakout_picks = {}
    
    print(f"🚀 Analyse Crypto 'Hyper-Momentum' sur {len(TICKERS)} actifs...")

    for ticker in TICKERS:
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            
            if len(df) < 200: continue
            
            # Nettoyage yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # --- CALCULS ---
            # SMA 200 : Tendance de fond
            df['SMA_200'] = calculate_sma(df['Close'], 200)
            
            # EMA 21 & EMA 50 : Support dynamique (Zone de rebond des cryptos fortes)
            df['EMA_21']  = calculate_ema(df['Close'], 21)
            df['EMA_50']  = calculate_ema(df['Close'], 50)
            
            df['RSI']     = calculate_rsi(df['Close'], 14)
            df['Vol_Avg'] = calculate_sma(df['Volume'], 20)

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = curr['Close']
            
            if pd.isna(curr['SMA_200']) or pd.isna(price) or price <= 0: continue

            # FILTRE 1 : PAS DE STABLECOINS (PRIX)
            if 0.98 <= price <= 1.02: continue

            clean_name = ticker.replace('-USD', '')
            clean_name = re.sub(r'\d+', '', clean_name)

            # ========================================================
            # STRATÉGIE 1 : PHOENIX (BREAKOUT EXPLOSIF)
            # ========================================================
            vol_ratio = curr['Volume'] / curr['Vol_Avg'] if (curr['Vol_Avg'] > 0) else 0
            
            # Conditions strictes :
            # 1. Tendance haussière confirmée (Prix > SMA 200)
            # 2. Bougie du jour verte et supérieure à la veille
            # 3. VOLUME MASSIF (> 2.0x la moyenne, on veut que ça explose)
            if (price > curr['SMA_200']) and (price > prev['Close']) and (vol_ratio > 2.0):
                score = ((price - curr['SMA_200']) / curr['SMA_200']) * 100
                stop_loss = min(prev['Low'], price * 0.88) # Stop -12%

                breakout_picks[ticker] = {
                    "name": clean_name,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "vol_ratio": round(vol_ratio, 1),
                    "history": df['Close'].tail(30).values.tolist()
                }

            # ========================================================
            # STRATÉGIE 2 : HYPER-PULLBACK (REBOND DE LEADER)
            # ========================================================
            # On cherche les leaders qui respirent, pas les morts qui coulent.
            
            # Condition 1 : FORCE DE TENDANCE
            # Le prix doit être nettement au-dessus de la SMA 200 (> 10%)
            # Cela élimine les cryptos "plates" comme LEO ou TRX.
            trend_strength = (price - curr['SMA_200']) / curr['SMA_200']
            
            # Condition 2 : LA ZONE D'ACHAT (Entre EMA 21 et EMA 50)
            # C'est là que les traders institutionnels rechargent en Bull Market.
            in_buy_zone = (price < curr['EMA_21']) and (price > curr['EMA_50'] * 0.98)
            
            # Condition 3 : RSI FROID
            # Le RSI doit avoir chuté (indiquant une correction) mais pas être en crash total
            rsi_valid = (35 < curr['RSI'] < 55)

            if (trend_strength > 0.10) and in_buy_zone and rsi_valid:
                # Score de qualité : Plus la tendance long terme est forte, mieux c'est
                score = trend_strength * 100
                
                # Stop Loss : Juste sous l'EMA 50 (le dernier rempart)
                stop_loss = curr['EMA_50'] * 0.92 

                pullback_picks[ticker] = {
                    "name": clean_name,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "history": df['Close'].tail(30).values.tolist()
                }
            
        except Exception:
            continue

    # Tri des résultats
    breakout_sorted = dict(sorted(breakout_picks.items(), key=lambda x: x[1]['vol_ratio'], reverse=True))
    
    # Pour le pullback, on trie par "Score" (ceux qui ont la plus forte tendance de fond en premier)
    pullback_sorted = dict(sorted(pullback_picks.items(), key=lambda x: x[1]['score'], reverse=True))

    return pullback_sorted, breakout_sorted

if __name__ == "__main__":
    pullback_data, breakout_data = analyze_market()
    today = pd.Timestamp.now().strftime("%d/%m/%Y")
    
    with open("data/crypto_pullback_pro.json", "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": pullback_data}, f, indent=4)
    with open("data/crypto_breakout_pro.json", "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": breakout_data}, f, indent=4)
        
    print("💾 Fichiers Crypto (Stratégie 2.0) sauvegardés.")
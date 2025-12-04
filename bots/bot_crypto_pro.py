import ccxt
import pandas as pd
import json
import time
import requests
import re

# --- CONFIGURATION ---
STABLECOINS = ["USDT", "USDC", "DAI", "FDUSD", "TUSA", "USDD", "PYUSD", "USDP", "EURI", "USDE", "BUSD", "USDS"]

# Initialisation des échanges (Lecture publique, pas besoin de clé API)
exchange_binance = ccxt.binance({'enableRateLimit': True})
exchange_gate = ccxt.gateio({'enableRateLimit': True}) # Gate.io a souvent les pépites introuvables ailleurs

# --- FONCTIONS TECHNIQUES ---
def calculate_sma(series, window):
    return series.rolling(window=window).mean()

def calculate_ema(series, window):
    return series.ewm(span=window, adjust=False).mean()

def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_top_cryptos(limit=150):
    """ Récupère le Top 150 CoinGecko et nettoie les symboles """
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 200, "page": 1, "sparkline": "false"}
    
    try:
        print(f"🔄 Connexion CoinGecko...")
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        symbols = []
        for coin in data:
            sym = coin['symbol'].upper()
            if sym in STABLECOINS: continue
            # Filtres anti-wrapped
            if sym.startswith("W") and sym in ["WBTC", "WETH", "WBNB"]: continue
            if "STETH" in sym: continue
            
            symbols.append(sym)
            
        return symbols[:limit]
    except Exception as e:
        print(f"⚠️ Erreur CoinGecko: {e}")
        return ["BTC", "ETH", "SOL", "BNB", "PEPE", "DOGE", "RNDR"]

def fetch_ohlcv(symbol):
    """ Essaie de trouver la crypto sur Binance, sinon Gate.io """
    pair = f"{symbol}/USDT"
    
    # 1. Essai Binance
    try:
        # Fetch 365 jours de bougies daily
        ohlcv = exchange_binance.fetch_ohlcv(pair, timeframe='1d', limit=365)
        if len(ohlcv) > 200:
            return pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    except:
        pass # Pas trouvé sur Binance, on continue

    # 2. Essai Gate.io (Pour les pépites)
    try:
        ohlcv = exchange_gate.fetch_ohlcv(pair, timeframe='1d', limit=365)
        if len(ohlcv) > 200:
            return pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    except:
        pass

    return None

def analyze_market():
    # On récupère les symboles propres (BTC, ETH, PEPE...)
    SYMBOLS = get_top_cryptos(150)
    
    pullback_picks = {}
    breakout_picks = {}
    
    print(f"🚀 Analyse CCXT (Multi-Exchange) sur {len(SYMBOLS)} actifs...")

    for symbol in SYMBOLS:
        # Pause pour respecter les rate limits des échanges
        time.sleep(0.1) 
        
        df = fetch_ohlcv(symbol)
        
        if df is None or df.empty:
            # print(f"❌ {symbol} introuvable sur Binance/Gate.")
            continue

        try:
            # --- CALCULS ---
            df['SMA_200'] = calculate_sma(df['Close'], 200)
            df['EMA_13']  = calculate_ema(df['Close'], 13)
            df['EMA_21']  = calculate_ema(df['Close'], 21)
            df['EMA_50']  = calculate_ema(df['Close'], 50)
            df['RSI']     = calculate_rsi(df['Close'], 14)
            df['Vol_Avg'] = calculate_sma(df['Volume'], 20)

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = curr['Close']
            
            if pd.isna(curr['SMA_200']) or price <= 0: continue

            # FILTRE PRIX (Anti-Stablecoin cachés)
            if 0.98 <= price <= 1.02: continue

            # ========================================================
            # STRATÉGIE 1 : PHOENIX (BREAKOUT)
            # ========================================================
            vol_ratio = curr['Volume'] / curr['Vol_Avg'] if (curr['Vol_Avg'] > 0) else 0
            
            # Conditions : Tendance Hausse + Bougie Verte + Volume > 1.3x
            if (price > curr['SMA_200']) and (price > prev['Close']) and (vol_ratio > 1.3):
                score = ((price - curr['SMA_200']) / curr['SMA_200']) * 100
                stop_loss = min(prev['Low'], price * 0.85) # Stop -15% max

                breakout_picks[symbol] = {
                    "name": symbol,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "vol_ratio": round(vol_ratio, 1),
                    "history": df['Close'].tail(30).values.tolist()
                }

            # ========================================================
            # STRATÉGIE 2 : PULLBACK (REBOND)
            # ========================================================
            trend_strength = (price - curr['SMA_200']) / curr['SMA_200']
            
            # Conditions :
            # 1. Forte Tendance de fond (> 5% au dessus SMA200)
            # 2. Repli en cours (Prix sous EMA 13)
            # 3. Support tient (Prix toujours au-dessus EMA 50)
            # 4. RSI sain (< 60)
            if (trend_strength > 0.05) and (price < curr['EMA_13']) and (price > curr['EMA_50']) and (curr['RSI'] < 60):
                score = trend_strength * 100
                stop_loss = curr['EMA_50'] * 0.90 # Stop -10% sous le support

                pullback_picks[symbol] = {
                    "name": symbol,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "history": df['Close'].tail(30).values.tolist()
                }
            
        except Exception:
            continue

    # Tri
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
        
    print("💾 Fichiers Crypto (Source CCXT) sauvegardés.")
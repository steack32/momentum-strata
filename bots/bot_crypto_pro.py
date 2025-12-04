import ccxt
import pandas as pd
import json
import time
import requests
import logging
import re
from typing import Dict, Tuple

# =========================
# CONFIGURATION "HAUTE SENSIBILITÉ"
# =========================

STABLECOINS = ["USDT", "USDC", "DAI", "FDUSD", "TUSA", "USDD", "PYUSD", "USDP", "EURI", "USDE", "BUSD", "USDS"]

# CRITÈRES ASSOUPLIS
MIN_CANDLES = 90              # On accepte les cryptos récentes (3 mois)
MIN_DOLLAR_VOL = 1_000_000    # 1M$ de volume journalier suffit (avant 5M$)
SLEEP_BETWEEN_CALLS = 0.2     # On ralentit un peu pour éviter le ban API

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("crypto_scanner")

# Exchanges
exchange_binance = ccxt.binance({'enableRateLimit': True})
exchange_gate = ccxt.gateio({'enableRateLimit': True})

# =========================
# FONCTIONS TECHNIQUES
# =========================

def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()

def calculate_ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()

def calculate_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def normalize(value: float, min_val: float, max_val: float, clip: bool = True) -> float:
    if max_val == min_val: return 0.0
    x = (value - min_val) / (max_val - min_val)
    if clip: x = max(0.0, min(1.0, x))
    return x

def get_top_cryptos(limit: int = 150):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 200, "page": 1, "sparkline": "false"}
    
    try:
        logger.info("Récupération liste CoinGecko...")
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        symbols = []
        for coin in data:
            sym = coin['symbol'].upper()
            if sym in STABLECOINS: continue
            if sym.startswith("W") and sym in ["WBTC", "WETH", "WBNB"]: continue
            if "STETH" in sym: continue
            
            symbols.append(sym)
            
        return symbols[:limit]
    except Exception as e:
        logger.warning(f"Erreur CoinGecko: {e}. Fallback.")
        return ["BTC", "ETH", "SOL", "BNB", "PEPE", "DOGE", "RNDR", "FET", "INJ", "SUI", "SEI", "TIA"]

def fetch_ohlcv(symbol: str) -> pd.DataFrame | None:
    pair = f"{symbol}/USDT"
    
    # On essaie Binance puis Gate
    for exchange, name in [(exchange_binance, "Binance"), (exchange_gate, "Gate.io")]:
        try:
            # On demande 200 bougies
            ohlcv = exchange.fetch_ohlcv(pair, timeframe='1d', limit=200)
            if not ohlcv: continue
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            
            # Vérification de l'âge de la dernière bougie (éviter les cryptos mortes/delistées)
            last_timestamp = df.iloc[-1]['timestamp']
            current_timestamp = int(time.time() * 1000)
            # Si la dernière bougie a plus de 48h, c'est une crypto morte ou delistée
            if (current_timestamp - last_timestamp) > 172800000: 
                # logger.debug(f"{symbol} ignoré (Données obsolètes sur {name})")
                continue

            if len(df) >= MIN_CANDLES:
                return df
        except Exception:
            continue

    return None

# =========================
# INDICATEURS
# =========================

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # On calcule la SMA 200 seulement si on a assez de data, sinon SMA 50
    if len(df) >= 200:
        df['SMA_200'] = calculate_sma(df['Close'], 200)
    else:
        # Pour les cryptos jeunes, la SMA 200 n'existe pas. On simule avec la SMA 90
        df['SMA_200'] = calculate_sma(df['Close'], 90)

    df['EMA_13']  = calculate_ema(df['Close'], 13)
    df['EMA_21']  = calculate_ema(df['Close'], 21)
    df['EMA_50']  = calculate_ema(df['Close'], 50)
    df['RSI']     = calculate_rsi(df['Close'], 14)
    df['Vol_Avg'] = calculate_sma(df['Volume'], 20)
    df['DollarVol'] = df['Close'] * df['Volume']
    df['DollarVol_Avg20'] = calculate_sma(df['DollarVol'], 20)
    df['High_20'] = df['High'].rolling(20).max()
    return df

def phoenix_breakout_score(curr: pd.Series, prev: pd.Series) -> float:
    price = curr['Close']
    sma200 = curr['SMA_200']
    rsi = curr['RSI']
    vol_ratio = curr['Volume'] / curr['Vol_Avg'] if curr['Vol_Avg'] > 0 else 0
    high_20 = curr['High_20']

    trend_pct = (price - sma200) / sma200
    # Score plus permissif sur la tendance
    trend_score = normalize(trend_pct, 0.0, 0.5) 
    # Volume : on valorise dès 1.2x
    vol_score = normalize(vol_ratio, 1.2, 4.0)
    rsi_score = normalize(rsi, 50, 75)

    if pd.isna(high_20) or high_20 == 0: high_score = 0
    else:
        dist = (high_20 - price) / high_20
        high_score = normalize(1 - dist, 0.85, 1.0)

    score = (0.35 * trend_score + 0.35 * vol_score + 0.15 * rsi_score + 0.15 * high_score)
    return score * 100

def pullback_score(curr: pd.Series) -> float:
    price = curr['Close']
    sma200 = curr['SMA_200']
    ema13 = curr['EMA_13']
    ema50 = curr['EMA_50']
    rsi = curr['RSI']

    trend_strength = (price - sma200) / sma200 
    
    # On cherche un prix qui est SOUS l'EMA 13 (Repli) mais pas trop loin de l'EMA 50
    # Plus on est proche de l'EMA 50, meilleur est le score de "rebond potentiel"
    dist_ema50 = (price - ema50) / ema50
    
    # Score de position : 100% si on est pile sur l'EMA 50, diminue si on s'éloigne
    position_score = normalize(1 - abs(dist_ema50), 0.95, 1.0)

    trend_score = normalize(trend_strength, 0.0, 0.5)
    rsi_score = normalize(rsi, 40, 60) 

    score = (0.4 * trend_score + 0.4 * position_score + 0.2 * rsi_score)
    return score * 100

def analyze_market() -> Tuple[Dict, Dict]:
    SYMBOLS = get_top_cryptos(150)
    
    pullback_picks = {}
    breakout_picks = {}

    logger.info(f"🚀 Analyse V3 (Haute Sensibilité) sur {len(SYMBOLS)} actifs...")

    for i, symbol in enumerate(SYMBOLS):
        # Petit sleep pour être gentil avec l'API
        if i % 10 == 0: time.sleep(SLEEP_BETWEEN_CALLS)
        
        df = fetch_ohlcv(symbol)
        if df is None or df.empty: continue

        try:
            df = compute_indicators(df)
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = curr['Close']

            if pd.isna(curr['SMA_200']) or price <= 0: continue
            if 0.98 <= price <= 1.02: continue # Stablecoin filter

            # Filtre Liquidité Assoupli (1M$)
            vol_usd = curr.get('DollarVol_Avg20', 0)
            if vol_usd < MIN_DOLLAR_VOL:
                # logger.debug(f"Rejet {symbol}: Volume faible ({vol_usd/1000:.0f}k$)")
                continue

            # =========================
            # STRAT 1 : PHOENIX (BREAKOUT)
            # =========================
            vol_ratio = curr['Volume'] / curr['Vol_Avg'] if curr['Vol_Avg'] > 0 else 0
            
            # Conditions ASSOUPLIES :
            # 1. Volume > 1.2x (Au lieu de 1.3x)
            # 2. Bougie verte (Close > Open) ou supérieure à la veille
            is_green = (price > curr['Open']) or (price > prev['Close'])
            # 3. Prix au-dessus de la SMA 200 (Tendance OK)
            in_trend = price > curr['SMA_200']

            if in_trend and is_green and (vol_ratio > 1.2):
                score = phoenix_breakout_score(curr, prev)
                stop_loss = min(prev['Low'], price * 0.90)

                breakout_picks[symbol] = {
                    "name": symbol,
                    "score": round(score, 2),
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "vol_ratio": round(vol_ratio, 2),
                    "rsi": round(curr['RSI'], 1),
                    "trend_pct": round((price - curr['SMA_200']) / curr['SMA_200'] * 100, 2),
                    "dollar_vol_avg20": round(vol_usd, 0),
                    "history": df['Close'].tail(30).round(6).tolist()
                }

            # =========================
            # STRAT 2 : PULLBACK (REBOND)
            # =========================
            trend_strength = (price - curr['SMA_200']) / curr['SMA_200']
            
            # Conditions ASSOUPLIES :
            # 1. Tendance positive (> 0%)
            # 2. Le prix est passé SOUS l'EMA 13 (C'est un repli)
            # 3. Le prix est ENCORE au-dessus de l'EMA 50 * 0.98 (On tolère une mèche de -2% sous le support)
            # 4. RSI < 60 (Pas en surchauffe)
            
            is_pulling_back = (price < curr['EMA_13'])
            is_holding_support = (price > curr['EMA_50'] * 0.98)
            
            if (trend_strength > 0) and is_pulling_back and is_holding_support and (curr['RSI'] < 60):
                score_pb = pullback_score(curr)
                stop_loss = curr['EMA_50'] * 0.90

                pullback_picks[symbol] = {
                    "name": symbol,
                    "score": round(score_pb, 2),
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "rsi": round(curr['RSI'], 1),
                    "trend_pct": round(trend_strength * 100, 2),
                    "dollar_vol_avg20": round(vol_usd, 0),
                    "history": df['Close'].tail(30).round(6).tolist()
                }

        except Exception as e:
            continue

    # Tri
    breakout_sorted = dict(sorted(breakout_picks.items(), key=lambda x: x[1]['score'], reverse=True))
    pullback_sorted = dict(sorted(pullback_picks.items(), key=lambda x: x[1]['score'], reverse=True))

    logger.info(f"✅ RÉSULTAT : {len(breakout_sorted)} Breakouts | {len(pullback_sorted)} Pullbacks")
    return pullback_sorted, breakout_sorted

if __name__ == "__main__":
    pullback_data, breakout_data = analyze_market()
    today = pd.Timestamp.now().strftime("%d/%m/%Y")
    
    with open("data/crypto_pullback_pro.json", "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": pullback_data}, f, indent=4)
    with open("data/crypto_breakout_pro.json", "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": breakout_data}, f, indent=4)
        
    print("💾 Fichiers Crypto sauvegardés.")
import ccxt
import pandas as pd
import json
import time
import requests
import logging
from typing import Dict, Tuple

# =========================
# CONFIG GLOBALE
# =========================

STABLECOINS = ["USDT", "USDC", "DAI", "FDUSD", "TUSA", "USDD", "PYUSD", "USDP", "EURI", "USDE", "BUSD", "USDS"]

MIN_CANDLES = 250             # Minimum de bougies daily pour considérer la paire
MIN_DOLLAR_VOL = 5_000_000    # Volume moyen en $ (20j) minimum
SLEEP_BETWEEN_CALLS = 0.1     # Pour respecter les rate limits

# Logger propre
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
    """
    Ramène une valeur entre 0 et 1 selon un intervalle [min_val, max_val].
    Si clip=True, on borne la valeur à [0, 1].
    """
    if max_val == min_val:
        return 0.0
    x = (value - min_val) / (max_val - min_val)
    if clip:
        x = max(0.0, min(1.0, x))
    return x

def get_top_cryptos(limit: int = 150):
    """ Récupère le Top CoinGecko et nettoie les symboles. """
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 200,
        "page": 1,
        "sparkline": "false"
    }
    
    try:
        logger.info("Connexion à CoinGecko pour récupérer le top market cap...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        symbols = []
        for coin in data:
            sym = coin['symbol'].upper()
            if sym in STABLECOINS:
                continue
            # Filtres anti-wrapped fréquents
            if sym.startswith("W") and sym in ["WBTC", "WETH", "WBNB"]:
                continue
            if "STETH" in sym:
                continue
            
            symbols.append(sym)
            
        logger.info(f"{len(symbols)} symboles récupérés sur CoinGecko.")
        return symbols[:limit]
    except Exception as e:
        logger.warning(f"Erreur CoinGecko: {e}. Fallback sur une liste fixe.")
        return ["BTC", "ETH", "SOL", "BNB", "PEPE", "DOGE", "RNDR"]

def fetch_ohlcv(symbol: str) -> pd.DataFrame | None:
    """
    Essaie de trouver la crypto sur Binance, sinon Gate.io.
    Renvoie un DataFrame OHLCV ou None.
    """
    pair = f"{symbol}/USDT"

    # Essai Binance
    for exchange, name in [(exchange_binance, "Binance"), (exchange_gate, "Gate.io")]:
        try:
            ohlcv = exchange.fetch_ohlcv(pair, timeframe='1d', limit=365)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            if len(df) >= MIN_CANDLES:
                logger.debug(f"{symbol} trouvé sur {name} avec {len(df)} bougies.")
                return df
        except Exception as e:
            logger.debug(f"{symbol} non trouvé sur {name} ou erreur: {e}")
            continue

    return None

# =========================
# STRATÉGIES & SCORING
# =========================

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['SMA_200'] = calculate_sma(df['Close'], 200)
    df['EMA_13']  = calculate_ema(df['Close'], 13)
    df['EMA_21']  = calculate_ema(df['Close'], 21)
    df['EMA_50']  = calculate_ema(df['Close'], 50)
    df['RSI']     = calculate_rsi(df['Close'], 14)
    df['Vol_Avg'] = calculate_sma(df['Volume'], 20)
    df['DollarVol'] = df['Close'] * df['Volume']
    df['DollarVol_Avg20'] = calculate_sma(df['DollarVol'], 20)
    df['High_20'] = df['High'].rolling(20).max()
    return df

def liquidity_filter(curr: pd.Series) -> bool:
    """
    Filtre liquidité : volume moyen 20j en $ minimum.
    """
    if pd.isna(curr.get('DollarVol_Avg20', None)):
        return False
    return curr['DollarVol_Avg20'] >= MIN_DOLLAR_VOL

def phoenix_breakout_score(curr: pd.Series, prev: pd.Series) -> float:
    """
    Score de breakout "Phoenix" :
    - tendance (distance à SMA200)
    - volume relatif
    - RSI
    - proximité du plus haut 20j
    """
    price = curr['Close']
    sma200 = curr['SMA_200']
    rsi = curr['RSI']
    vol_ratio = curr['Volume'] / curr['Vol_Avg'] if curr['Vol_Avg'] > 0 else 0
    high_20 = curr['High_20']

    # 1) Tendance : on cherche 5% à 50% au-dessus de la SMA 200
    trend_pct = (price - sma200) / sma200
    trend_score = normalize(trend_pct, 0.05, 0.5)

    # 2) Volume : ratio 1.3x à 3x
    vol_score = normalize(vol_ratio, 1.3, 3.0)

    # 3) RSI : idéalement 55–70
    rsi_score = normalize(rsi, 55, 70)

    # 4) Proximité du plus haut 20j (plus on est proche, mieux c’est)
    if pd.isna(high_20) or high_20 == 0:
        high_score = 0
    else:
        dist_to_high = (high_20 - price) / high_20  # 0 = sur le high, 0.1 = 10% en dessous
        high_score = normalize(1 - dist_to_high, 0.8, 1.0)  # on privilégie 0–20% sous les plus hauts

    # Pondération (tu peux ajuster)
    score = (
        0.35 * trend_score +
        0.30 * vol_score +
        0.20 * rsi_score +
        0.15 * high_score
    )
    return score * 100  # pour rester sur un score "lisible"

def pullback_score(curr: pd.Series) -> float:
    """
    Score pullback :
    - force de tendance (distance SMA200)
    - profondeur du repli entre EMA13 et EMA50
    - RSI dans une zone "saine"
    """
    price = curr['Close']
    sma200 = curr['SMA_200']
    ema13 = curr['EMA_13']
    ema50 = curr['EMA_50']
    rsi = curr['RSI']

    trend_strength = (price - sma200) / sma200  # > 0.05 normalement

    # Repli : on veut que le prix soit entre EMA13 et EMA50
    # on normalise la position du prix dans ce canal
    if ema13 == ema50:
        pullback_pos = 0.5
    else:
        pullback_pos = (price - ema50) / (ema13 - ema50)
        # On veut idéalement un prix vers le milieu du canal (ni collé à EMA13 ni EMA50)
        pullback_pos = 1 - abs(pullback_pos - 0.5) * 2  # 1 si milieu, 0 si extrémité

    trend_score = normalize(trend_strength, 0.05, 0.5)
    rsi_score = normalize(rsi, 45, 60)  # RSI ni trop faible ni trop haut

    score = (
        0.5 * trend_score +
        0.3 * pullback_pos +
        0.2 * rsi_score
    )
    return score * 100

def analyze_market() -> Tuple[Dict, Dict]:
    SYMBOLS = get_top_cryptos(150)
    
    pullback_picks = {}
    breakout_picks = {}

    logger.info(f"Analyse sur {len(SYMBOLS)} actifs potentiels...")

    for i, symbol in enumerate(SYMBOLS, 1):
        time.sleep(SLEEP_BETWEEN_CALLS)
        logger.debug(f"[{i}/{len(SYMBOLS)}] Traitement de {symbol}...")
        
        df = fetch_ohlcv(symbol)
        if df is None or df.empty:
            continue

        try:
            df = compute_indicators(df)
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = curr['Close']

            # SMA200 dispo & prix > 0
            if pd.isna(curr['SMA_200']) or price <= 0:
                continue

            # Filtre "stablecoin déguisé"
            if 0.98 <= price <= 1.02:
                continue

            # Filtre liquidité
            if not liquidity_filter(curr):
                logger.debug(f"{symbol} rejeté pour manque de liquidité (DollarVol_Avg20={curr['DollarVol_Avg20']:.0f}).")
                continue

            # =========================
            # STRAT PHOENIX (BREAKOUT)
            # =========================

            vol_ratio = curr['Volume'] / curr['Vol_Avg'] if curr['Vol_Avg'] > 0 else 0
            in_trend = price > curr['SMA_200']
            green_candle = price > prev['Close']
            volume_ok = vol_ratio > 1.3

            if in_trend and green_candle and volume_ok:
                score = phoenix_breakout_score(curr, prev)

                # Stop-loss : min(low d'hier, -15 %)
                stop_loss = min(prev['Low'], price * 0.85)

                breakout_picks[symbol] = {
                    "name": symbol,
                    "score": round(score, 2),
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "vol_ratio": round(vol_ratio, 2),
                    "rsi": round(curr['RSI'], 1),
                    "trend_pct": round((price - curr['SMA_200']) / curr['SMA_200'] * 100, 2),
                    "dollar_vol_avg20": round(curr['DollarVol_Avg20'], 0),
                    "history": df['Close'].tail(30).round(6).tolist()
                }

            # =========================
            # STRAT PULLBACK (REBOND)
            # =========================

            trend_strength = (price - curr['SMA_200']) / curr['SMA_200']

            if (
                trend_strength > 0.05 and
                price < curr['EMA_13'] and
                price > curr['EMA_50'] and
                curr['RSI'] < 60
            ):
                score_pb = pullback_score(curr)
                stop_loss = curr['EMA_50'] * 0.90  # 10 % sous EMA50

                pullback_picks[symbol] = {
                    "name": symbol,
                    "score": round(score_pb, 2),
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "rsi": round(curr['RSI'], 1),
                    "trend_pct": round(trend_strength * 100, 2),
                    "dollar_vol_avg20": round(curr['DollarVol_Avg20'], 0),
                    "history": df['Close'].tail(30).round(6).tolist()
                }

        except Exception as e:
            logger.warning(f"Erreur sur {symbol}: {e}")
            continue

    breakout_sorted = dict(sorted(breakout_picks.items(), key=lambda x: x[1]['score'], reverse=True))
    pullback_sorted = dict(sorted(pullback_picks.items(), key=lambda x: x[1]['score'], reverse=True))

    logger.info(f"{len(breakout_sorted)} signaux breakout, {len(pullback_sorted)} signaux pullback retenus.")
    return pullback_sorted, breakout_sorted


if __name__ == "__main__":
    pullback_data, breakout_data = analyze_market()
    today = pd.Timestamp.now().strftime("%d/%m/%Y")

    result_pullback = {
        "date_mise_a_jour": today,
        "params": {
            "min_dollar_vol": MIN_DOLLAR_VOL,
            "min_candles": MIN_CANDLES
        },
        "picks": pullback_data
    }
    result_breakout = {
        "date_mise_a_jour": today,
        "params": {
            "min_dollar_vol": MIN_DOLLAR_VOL,
            "min_candles": MIN_CANDLES
        },
        "picks": breakout_data
    }

    with open("data/crypto_pullback_pro.json", "w") as f:
        json.dump(result_pullback, f, indent=4)
    with open("data/crypto_breakout_pro.json", "w") as f:
        json.dump(result_breakout, f, indent=4)

    logger.info("Fichiers Crypto (Source CCXT) sauvegardés.")

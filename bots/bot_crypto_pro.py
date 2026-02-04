import ccxt
import pandas as pd
import json
import time
import requests
import logging
from typing import Dict, Tuple

from config import (
    DATA_DIR,
    BREAKOUT_FILE_CRYPTO,
    PULLBACK_FILE_CRYPTO,
    CRYPTO_MIN_CANDLES,
    CRYPTO_MIN_DOLLAR_VOL,
    CRYPTO_SLEEP_BETWEEN_CALLS,
    CRYPTO_STABLECOINS,
    CRYPTO_EXCLUDED_SYMBOLS,
    CRYPTO_EXCLUDED_NAME_KEYWORDS,
    CRYPTO_FALLBACK_MAX_BREAKOUT,
    CRYPTO_FALLBACK_MAX_PULLBACK,
)
from indicators import calculate_sma, calculate_ema, calculate_rsi, normalize

# =========================
# CONFIGURATION LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("crypto_scanner")

exchange_binance = ccxt.binance({"enableRateLimit": True})


# =========================
# RÉCUPÉRATION LISTE CRYPTOS
# =========================

def get_top_cryptos(limit: int = 150):
    """
    Top market cap CoinGecko, filtré :
    - stablecoins
    - tokens blacklistés (XAUT, PAXG, BDX, etc.)
    - noms "gold-like"
    """
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 200,
        "page": 1,
        "sparkline": "false"
    }

    try:
        logger.info("Récupération liste CoinGecko...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        symbols = []
        for coin in data:
            sym = coin["symbol"].upper()
            name = coin.get("name", "").upper()

            if sym in CRYPTO_STABLECOINS:
                continue
            if sym in CRYPTO_EXCLUDED_SYMBOLS:
                continue
            if any(keyword in name for keyword in CRYPTO_EXCLUDED_NAME_KEYWORDS):
                continue
            if sym.startswith("W") and sym in ["WBTC", "WETH", "WBNB"]:
                continue
            if "STETH" in sym:
                continue

            symbols.append(sym)

        logger.info(f"{len(symbols)} actifs retenus après filtre univers.")
        return symbols[:limit]
    except Exception as e:
        logger.warning(f"Erreur CoinGecko: {e}. Fallback liste réduite.")
        return ["BTC", "ETH", "SOL", "BNB", "PEPE", "DOGE", "RNDR", "FET", "INJ", "SUI", "SEI", "TIA"]


def fetch_ohlcv(symbol: str) -> pd.DataFrame | None:
    """
    OHLCV daily sur Binance.
    On filtre les actifs avec données trop vieilles.
    """
    pair = f"{symbol}/USDT"

    try:
        ohlcv = exchange_binance.fetch_ohlcv(pair, timeframe="1d", limit=200)
        if not ohlcv:
            return None

        df = pd.DataFrame(ohlcv, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
        last_timestamp = df.iloc[-1]["timestamp"]
        current_timestamp = int(time.time() * 1000)

        # Données > 48h => on jette
        if (current_timestamp - last_timestamp) > 172800000:
            return None

        if len(df) >= CRYPTO_MIN_CANDLES:
            return df
    except Exception:
        return None

    return None


# =========================
# INDICATEURS
# =========================

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if len(df) >= 200:
        df["SMA_200"] = calculate_sma(df["Close"], 200)
    else:
        df["SMA_200"] = calculate_sma(df["Close"], 90)

    df["EMA_13"] = calculate_ema(df["Close"], 13)
    df["EMA_21"] = calculate_ema(df["Close"], 21)
    df["EMA_50"] = calculate_ema(df["Close"], 50)
    df["RSI"] = calculate_rsi(df["Close"], 14, method="ema")
    df["Vol_Avg"] = calculate_sma(df["Volume"], 20)
    df["DollarVol"] = df["Close"] * df["Volume"]
    df["DollarVol_Avg20"] = calculate_sma(df["DollarVol"], 20)
    df["High_20"] = df["High"].rolling(20).max()
    return df


def phoenix_breakout_score(curr: pd.Series, prev: pd.Series) -> float:
    price = curr["Close"]
    sma200 = curr["SMA_200"]
    rsi = curr["RSI"]
    vol_ratio = curr["Volume"] / curr["Vol_Avg"] if curr["Vol_Avg"] > 0 else 0
    high_20 = curr["High_20"]

    trend_pct = (price - sma200) / sma200
    trend_score = normalize(trend_pct, 0.0, 0.5)
    vol_score = normalize(vol_ratio, 1.2, 4.0)
    rsi_score = normalize(rsi, 50, 75)

    if pd.isna(high_20) or high_20 == 0:
        high_score = 0
    else:
        dist = (high_20 - price) / high_20
        high_score = normalize(1 - dist, 0.85, 1.0)

    score = (0.35 * trend_score + 0.35 * vol_score + 0.15 * rsi_score + 0.15 * high_score)
    return score * 100


def pullback_score(curr: pd.Series) -> float:
    price = curr["Close"]
    sma200 = curr["SMA_200"]
    ema50 = curr["EMA_50"]
    rsi = curr["RSI"]

    trend_strength = (price - sma200) / sma200
    dist_ema50 = (price - ema50) / ema50

    position_score = normalize(1 - abs(dist_ema50), 0.95, 1.0)
    trend_score = normalize(trend_strength, 0.0, 0.5)
    rsi_score = normalize(rsi, 40, 60)

    score = (0.4 * trend_score + 0.4 * position_score + 0.2 * rsi_score)
    return score * 100


# =========================
# LOGIQUE D'ANALYSE + FALLBACK
# =========================

def analyze_market() -> Tuple[Dict, Dict]:
    SYMBOLS = get_top_cryptos(150)

    pullback_picks: Dict[str, Dict] = {}
    breakout_picks: Dict[str, Dict] = {}

    fallback_breakout_candidates = []
    fallback_pullback_candidates = []

    nb_processed = 0

    logger.info(f"Analyse crypto sur {len(SYMBOLS)} actifs...")

    for i, symbol in enumerate(SYMBOLS):
        if i % 10 == 0:
            time.sleep(CRYPTO_SLEEP_BETWEEN_CALLS)

        df = fetch_ohlcv(symbol)
        if df is None or df.empty:
            continue

        try:
            df = compute_indicators(df)
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = curr["Close"]

            if pd.isna(curr["SMA_200"]) or price <= 0:
                continue
            if 0.98 <= price <= 1.02:
                continue

            vol_usd = curr.get("DollarVol_Avg20", 0)
            if pd.isna(vol_usd) or vol_usd < CRYPTO_MIN_DOLLAR_VOL:
                continue

            nb_processed += 1

            trend_strength = (price - curr["SMA_200"]) / curr["SMA_200"]
            vol_ratio = curr["Volume"] / curr["Vol_Avg"] if curr["Vol_Avg"] > 0 else 0
            is_green = (price > curr["Open"]) or (price > prev["Close"])
            in_trend = price > curr["SMA_200"]

            phoenix_score_val = phoenix_breakout_score(curr, prev)
            pullback_score_val = pullback_score(curr)

            # --- CANDIDATS FALLBACK ---
            if trend_strength > -0.2 and curr["RSI"] < 80:
                fallback_breakout_candidates.append({
                    "symbol": symbol,
                    "score": phoenix_score_val,
                    "price": price,
                    "rsi": float(curr["RSI"]),
                    "trend_pct": float(trend_strength * 100),
                    "vol_ratio": float(vol_ratio),
                    "dollar_vol_avg20": float(vol_usd),
                    "stop_loss": min(prev["Low"], price * 0.90),
                    "history": df["Close"].tail(30).round(6).tolist()
                })

            if trend_strength > -0.3 and curr["RSI"] < 75:
                fallback_pullback_candidates.append({
                    "symbol": symbol,
                    "score": pullback_score_val,
                    "price": price,
                    "rsi": float(curr["RSI"]),
                    "trend_pct": float(trend_strength * 100),
                    "dollar_vol_avg20": float(vol_usd),
                    "stop_loss": float(curr["EMA_50"] * 0.9),
                    "history": df["Close"].tail(30).round(6).tolist()
                })

            # --- CONDITIONS STRICTES ---
            if in_trend and is_green and (vol_ratio > 1.2):
                stop_loss = min(prev["Low"], price * 0.90)

                breakout_picks[symbol] = {
                    "name": symbol,
                    "score": round(phoenix_score_val, 2),
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "vol_ratio": round(vol_ratio, 2),
                    "rsi": round(curr["RSI"], 1),
                    "trend_pct": round(trend_strength * 100, 2),
                    "dollar_vol_avg20": round(vol_usd, 0),
                    "history": df["Close"].tail(30).round(6).tolist()
                }

            is_pulling_back = (price < curr["EMA_13"])
            is_holding_support = (price > curr["EMA_50"] * 0.98)

            if (trend_strength > 0) and is_pulling_back and is_holding_support and (curr["RSI"] < 60):
                stop_loss_pb = curr["EMA_50"] * 0.90

                pullback_picks[symbol] = {
                    "name": symbol,
                    "score": round(pullback_score_val, 2),
                    "entry_price": price,
                    "stop_loss": stop_loss_pb,
                    "rsi": round(curr["RSI"], 1),
                    "trend_pct": round(trend_strength * 100, 2),
                    "dollar_vol_avg20": round(vol_usd, 0),
                    "history": df["Close"].tail(30).round(6).tolist()
                }

        except Exception:
            continue

    logger.info(f"Actifs analysés (liquidité & data OK) : {nb_processed}")
    logger.info(f"Candidats fallback : {len(fallback_breakout_candidates)} breakouts, {len(fallback_pullback_candidates)} pullbacks.")
    logger.info(f"Signaux stricts : {len(breakout_picks)} breakouts, {len(pullback_picks)} pullbacks.")

    # ================
    # FALLBACK
    # ================

    if not breakout_picks and fallback_breakout_candidates:
        logger.info("Aucun breakout strict. On utilise le fallback.")
        fallback_breakout_candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in fallback_breakout_candidates[:CRYPTO_FALLBACK_MAX_BREAKOUT]:
            breakout_picks[cand["symbol"]] = {
                "name": cand["symbol"],
                "score": round(cand["score"], 2),
                "entry_price": cand["price"],
                "stop_loss": cand["stop_loss"],
                "vol_ratio": round(cand["vol_ratio"], 2),
                "rsi": round(cand["rsi"], 1),
                "trend_pct": round(cand["trend_pct"], 2),
                "dollar_vol_avg20": round(cand["dollar_vol_avg20"], 0),
                "history": cand["history"]
            }

    if not pullback_picks and fallback_pullback_candidates:
        logger.info("Aucun pullback strict. On utilise le fallback.")
        fallback_pullback_candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in fallback_pullback_candidates[:CRYPTO_FALLBACK_MAX_PULLBACK]:
            pullback_picks[cand["symbol"]] = {
                "name": cand["symbol"],
                "score": round(cand["score"], 2),
                "entry_price": cand["price"],
                "stop_loss": cand["stop_loss"],
                "rsi": round(cand["rsi"], 1),
                "trend_pct": round(cand["trend_pct"], 2),
                "dollar_vol_avg20": round(cand["dollar_vol_avg20"], 0),
                "history": cand["history"]
            }

    breakout_sorted = dict(sorted(breakout_picks.items(), key=lambda x: x[1]["score"], reverse=True))
    pullback_sorted = dict(sorted(pullback_picks.items(), key=lambda x: x[1]["score"], reverse=True))

    logger.info(f"RÉSULTAT FINAL : {len(breakout_sorted)} Breakouts | {len(pullback_sorted)} Pullbacks")
    return pullback_sorted, breakout_sorted


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    pullback_data, breakout_data = analyze_market()
    today = pd.Timestamp.now().strftime("%d/%m/%Y")

    print(f"Nb breakouts crypto : {len(breakout_data)}")
    print(f"Nb pullbacks crypto : {len(pullback_data)}")

    with open(PULLBACK_FILE_CRYPTO, "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": pullback_data}, f, indent=4)
    with open(BREAKOUT_FILE_CRYPTO, "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": breakout_data}, f, indent=4)

    print("Fichiers Crypto sauvegardés.")

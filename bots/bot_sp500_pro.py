from __future__ import annotations

import os
import json
import time
import logging
import requests
from typing import Dict, Tuple

import pandas as pd
import yfinance as yf

from config import (
    DATA_DIR,
    BREAKOUT_FILE_SP500,
    PULLBACK_FILE_SP500,
    SP500_MIN_CANDLES,
    SP500_MIN_DOLLAR_VOL,
    SP500_SLEEP_BETWEEN_CALLS,
)
from indicators import calculate_sma, calculate_rsi, normalize

# =========================
# CONFIGURATION LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sp500_scanner")


# =========================
# RÉCUPÉRATION TICKERS & NOMS
# =========================

def get_sp500_tickers() -> Dict[str, str]:
    """
    Récupère un dictionnaire {Ticker: Nom de la société} depuis Wikipédia.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        logger.info("Récupération S&P 500 (Tickers + Noms)...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        tables = pd.read_html(response.text)
        df = tables[0]

        tickers_map = {}
        for index, row in df.iterrows():
            ticker = row["Symbol"].replace(".", "-")
            name = row["Security"]
            tickers_map[ticker] = name

        logger.info(f"{len(tickers_map)} sociétés récupérées.")
        return tickers_map

    except Exception as e:
        logger.warning(f"Échec Wikipédia: {e}. Fallback.")
        return {
            "AAPL": "Apple Inc.", "MSFT": "Microsoft", "GOOGL": "Alphabet",
            "AMZN": "Amazon", "NVDA": "Nvidia", "TSLA": "Tesla", "META": "Meta Platforms"
        }


# =========================
# DATA YFINANCE
# =========================

def fetch_ohlcv_yf(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(
            ticker, period="2y", interval="1d", auto_adjust=False, progress=False, threads=False
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            try:
                df.columns = df.columns.get_level_values(0)
            except:
                pass

        if 'Close' not in df.columns and 'Adj Close' in df.columns:
            df['Close'] = df['Adj Close']

        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required):
            return None
        if len(df) < SP500_MIN_CANDLES:
            return None

        return df
    except Exception:
        return None


# =========================
# INDICATEURS
# =========================

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["SMA_200"] = calculate_sma(df["Close"], 200)
    df["SMA_50"] = calculate_sma(df["Close"], 50)
    df["RSI"] = calculate_rsi(df["Close"], 14)
    df["Vol_Avg"] = calculate_sma(df["Volume"], 20)
    df["DollarVol"] = df["Close"] * df["Volume"]
    df["DollarVol_Avg20"] = calculate_sma(df["DollarVol"], 20)
    df["High_20"] = df["High"].rolling(20).max()
    return df


def liquidity_filter(curr: pd.Series) -> bool:
    if pd.isna(curr.get("DollarVol_Avg20", None)):
        return False
    return curr["DollarVol_Avg20"] >= SP500_MIN_DOLLAR_VOL


# =========================
# SCORING
# =========================

def phoenix_breakout_score(curr: pd.Series, prev: pd.Series) -> float:
    price = curr["Close"]
    sma200 = curr["SMA_200"]
    rsi = curr["RSI"]
    vol_ratio = curr["Volume"] / curr["Vol_Avg"] if curr["Vol_Avg"] > 0 else 0
    high_20 = curr["High_20"]

    trend_pct = (price - sma200) / sma200
    trend_score = normalize(trend_pct, 0.03, 0.4)
    vol_score = normalize(vol_ratio, 2.0, 5.0)
    rsi_score = normalize(rsi, 55, 70)

    if pd.isna(high_20) or high_20 == 0:
        high_score = 0
    else:
        dist = (high_20 - price) / high_20
        high_score = normalize(1 - dist, 0.8, 1.0)

    score = (0.40 * trend_score + 0.30 * vol_score + 0.20 * rsi_score + 0.10 * high_score)
    return score * 100.0


def pullback_score(curr: pd.Series) -> float:
    price = curr["Close"]
    sma200 = curr["SMA_200"]
    sma50 = curr["SMA_50"]
    rsi = curr["RSI"]

    trend_strength = (price - sma200) / sma200
    trend_score = normalize(trend_strength, 0.05, 0.4)

    if sma50 == 0 or pd.isna(sma50):
        pb_score = 0
    else:
        dist = abs((price - sma50) / sma50)
        pb_score = normalize(0.03 - dist, 0.0, 0.03)

    rsi_score = normalize(rsi, 45, 60)

    score = (0.5 * trend_score + 0.3 * pb_score + 0.2 * rsi_score)
    return score * 100.0


# =========================
# ANALYSE
# =========================

def analyze_market() -> Tuple[Dict, Dict]:
    tickers_map = get_sp500_tickers()

    pullback_picks = {}
    breakout_picks = {}

    logger.info(f"Analyse S&P 500 sur {len(tickers_map)} sociétés...")

    for i, (ticker, company_name) in enumerate(tickers_map.items(), 1):
        if i % 20 == 0:
            time.sleep(SP500_SLEEP_BETWEEN_CALLS)

        df = fetch_ohlcv_yf(ticker)
        if df is None:
            continue

        try:
            df = compute_indicators(df)
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = float(curr["Close"])

            if pd.isna(curr["SMA_200"]) or price <= 0:
                continue
            if not liquidity_filter(curr):
                continue

            # --- BREAKOUT ---
            vol_ratio = curr["Volume"] / curr["Vol_Avg"] if curr["Vol_Avg"] > 0 else 0
            if (price > curr["SMA_200"]) and (price > float(prev["Close"])) and (vol_ratio > 2.0):
                score_br = phoenix_breakout_score(curr, prev)
                stop_loss = min(float(prev["Low"]), price * 0.95)

                breakout_picks[ticker] = {
                    "name": company_name,
                    "ticker": ticker,
                    "score": round(score_br, 2),
                    "entry_price": round(price, 2),
                    "stop_loss": round(stop_loss, 2),
                    "vol_ratio": round(vol_ratio, 2),
                    "rsi": round(float(curr["RSI"]), 1),
                    "trend_pct": round(((price - curr["SMA_200"]) / curr["SMA_200"]) * 100, 2),
                    "history": df["Close"].tail(30).round(2).tolist(),
                }

            # --- PULLBACK ---
            sma50 = curr["SMA_50"]
            trend = (price - curr["SMA_200"]) / curr["SMA_200"]
            near_sma50 = (not pd.isna(sma50) and abs((price - sma50) / sma50) <= 0.03)

            if trend > 0.05 and near_sma50 and curr["RSI"] < 60:
                score_pb = pullback_score(curr)
                stop_loss = sma50 * 0.95

                pullback_picks[ticker] = {
                    "name": company_name,
                    "ticker": ticker,
                    "score": round(score_pb, 2),
                    "entry_price": round(price, 2),
                    "stop_loss": round(stop_loss, 2),
                    "rsi": round(float(curr["RSI"]), 1),
                    "trend_pct": round(trend * 100, 2),
                    "history": df["Close"].tail(30).round(2).tolist(),
                }

        except Exception:
            continue

    # Tris
    breakout_sorted = dict(sorted(breakout_picks.items(), key=lambda x: x[1]["score"], reverse=True))
    pullback_sorted = dict(sorted(pullback_picks.items(), key=lambda x: x[1]["score"], reverse=True))

    # Top 5 pullback
    pullback_top5 = dict(list(pullback_sorted.items())[:5])

    logger.info(f"{len(breakout_sorted)} breakouts | {len(pullback_top5)} pullbacks (Top 5)")
    return pullback_top5, breakout_sorted


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    pb_data, br_data = analyze_market()
    today = pd.Timestamp.now().strftime("%d/%m/%Y")

    with open(PULLBACK_FILE_SP500, "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": pb_data}, f, indent=4)

    with open(BREAKOUT_FILE_SP500, "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": br_data}, f, indent=4)

    logger.info("Fichiers sauvegardés.")

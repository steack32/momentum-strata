from __future__ import annotations

import os
import json
import time
import logging
from typing import Dict, Tuple, List

import pandas as pd
import yfinance as yf

# =========================
# CONFIG GLOBALE
# =========================

MIN_CANDLES = 220             # Minimum de bougies daily pour considérer la série
MIN_DOLLAR_VOL = 5_000_000    # Volume moyen en $ (20j) minimum
SLEEP_BETWEEN_CALLS = 0.05    # Pauses entre les appels pour éviter de spammer l'API

DATA_DIR = "data"
PULLBACK_FILE = os.path.join(DATA_DIR, "sp500_pullback_pro.json")
BREAKOUT_FILE = os.path.join(DATA_DIR, "sp500_breakout_pro.json")

# Logger propre
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sp500_scanner")


# =========================
# FONCTIONS TECHNIQUES
# =========================

def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def calculate_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


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


# =========================
# RÉCUPÉRATION DES TICKERS S&P 500
# =========================

def get_sp500_tickers() -> List[str]:
    """
    Récupère les tickers S&P 500 depuis Wikipédia.
    Fallback possible si l'appel échoue.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        logger.info("Récupération des tickers S&P 500 depuis Wikipédia...")
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df["Symbol"].tolist()

        # Format Yahoo : BRK.B -> BRK-B, BF.B -> BF-B, etc.
        tickers = [t.replace(".", "-") for t in tickers]

        logger.info(f"{len(tickers)} tickers S&P 500 récupérés.")
        return tickers
    except Exception as e:
        logger.warning(f"Échec de récupération S&P 500 depuis Wikipédia: {e}")
        # Fallback minimal si Wikipédia ne répond pas (à compléter si besoin)
        fallback = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "BRK-B", "JPM", "UNH"]
        logger.info(f"Utilisation de la liste fallback : {fallback}")
        return fallback


# =========================
# DATA YFINANCE
# =========================

def fetch_ohlcv_yf(ticker: str) -> pd.DataFrame | None:
    """
    Récupère les données daily pour un ticker via yfinance.
    On prend 2 ans d'historique pour avoir une SMA200 plus propre.
    """
    try:
        df = yf.download(
            ticker,
            period="2y",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            # Cas multi-ticker, normalement ne devrait pas arriver ici, mais on sécurise
            df = df["Close"].to_frame(name="Close").join(
                df["Open"].to_frame(name="Open")
            ).join(
                df["High"].to_frame(name="High")
            ).join(
                df["Low"].to_frame(name="Low")
            ).join(
                df["Volume"].to_frame(name="Volume")
            )

        # On s'assure d'avoir les colonnes standard
        expected_cols = {"Open", "High", "Low", "Close", "Volume"}
        if not expected_cols.issubset(df.columns):
            return None

        if len(df) < MIN_CANDLES:
            return None

        return df
    except Exception as e:
        logger.debug(f"Erreur yfinance sur {ticker}: {e}")
        return None


# =========================
# INDICATEURS & FILTRES
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
    """
    Filtre liquidité : volume moyen 20j en $ minimum.
    """
    if pd.isna(curr.get("DollarVol_Avg20", None)):
        return False
    return curr["DollarVol_Avg20"] >= MIN_DOLLAR_VOL


# =========================
# SCORING STRATÉGIES
# =========================

def phoenix_breakout_score(curr: pd.Series, prev: pd.Series) -> float:
    """
    Score de breakout type "Phoenix" :
    - tendance (distance à SMA200)
    - volume relatif
    - RSI
    - proximité du plus haut 20j
    """
    price = curr["Close"]
    sma200 = curr["SMA_200"]
    rsi = curr["RSI"]
    vol_ratio = curr["Volume"] / curr["Vol_Avg"] if curr["Vol_Avg"] and curr["Vol_Avg"] > 0 else 0
    high_20 = curr["High_20"]

    # 1) Tendance : on cherche 3% à 40% au-dessus de la SMA 200
    trend_pct = (price - sma200) / sma200
    trend_score = normalize(trend_pct, 0.03, 0.4)

    # 2) Volume : ratio 2x à 5x
    vol_score = normalize(vol_ratio, 2.0, 5.0)

    # 3) RSI : idéalement 55–70
    rsi_score = normalize(rsi, 55, 70)

    # 4) Proximité du plus haut 20j (plus on est proche, mieux c’est)
    if pd.isna(high_20) or high_20 == 0:
        high_score = 0
    else:
        dist_to_high = (high_20 - price) / high_20  # 0 = sur le high, 0.1 = 10% en dessous
        high_score = normalize(1 - dist_to_high, 0.8, 1.0)  # on privilégie 0–20% sous les plus hauts

    # Pondération
    score = (
        0.40 * trend_score +
        0.30 * vol_score +
        0.20 * rsi_score +
        0.10 * high_score
    )
    return score * 100.0


def pullback_score(curr: pd.Series) -> float:
    """
    Score pullback :
    - force de tendance (distance SMA200)
    - profondeur et qualité du repli autour de la SMA50
    - RSI dans une zone "saine"
    """
    price = curr["Close"]
    sma200 = curr["SMA_200"]
    sma50 = curr["SMA_50"]
    rsi = curr["RSI"]

    trend_strength = (price - sma200) / sma200  # > 0.05 normalement
    trend_score = normalize(trend_strength, 0.05, 0.4)

    # Proximité de la SMA50
    if sma50 == 0 or pd.isna(sma50):
        pullback_pos_score = 0
    else:
        dist_sma50 = abs((price - sma50) / sma50)  # 0 = pile sur sma50
        # On veut idéalement <= 3%
        pullback_pos_score = normalize(0.03 - dist_sma50, 0.0, 0.03)

    # RSI : idéalement entre 45 et 60
    rsi_score = normalize(rsi, 45, 60)

    score = (
        0.5 * trend_score +
        0.3 * pullback_pos_score +
        0.2 * rsi_score
    )
    return score * 100.0


# =========================
# ANALYSE MARCHÉ
# =========================

def analyze_market() -> Tuple[Dict, Dict]:
    tickers = get_sp500_tickers()

    pullback_picks: Dict[str, Dict] = {}
    breakout_picks: Dict[str, Dict] = {}

    logger.info(f"Analyse S&P 500 sur {len(tickers)} tickers...")

    for i, ticker in enumerate(tickers, 1):
        time.sleep(SLEEP_BETWEEN_CALLS)
        logger.debug(f"[{i}/{len(tickers)}] Traitement de {ticker}...")

        df = fetch_ohlcv_yf(ticker)
        if df is None or df.empty:
            continue

        try:
            df = compute_indicators(df)

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = float(curr["Close"])

            # SMA200 dispo & prix > 0
            if pd.isna(curr["SMA_200"]) or price <= 0:
                continue

            # Filtre liquidité
            if not liquidity_filter(curr):
                logger.debug(
                    f"{ticker} rejeté (DollarVol_Avg20={curr['DollarVol_Avg20']:.0f} < {MIN_DOLLAR_VOL})."
                )
                continue

            # ====================================================
            # STRAT 1 : BREAKOUT (PHOENIX)
            # ====================================================
            vol_ratio = (
                curr["Volume"] / curr["Vol_Avg"]
                if curr["Vol_Avg"] and curr["Vol_Avg"] > 0 else 0
            )
            in_trend = price > curr["SMA_200"]
            green_candle = price > float(prev["Close"])
            volume_ok = vol_ratio > 2.0

            if in_trend and green_candle and volume_ok:
                score_br = phoenix_breakout_score(curr, prev)
                trend_pct = (price - curr["SMA_200"]) / curr["SMA_200"] * 100.0

                # Stop-loss : min(low d’hier, -5 %)
                stop_loss = min(float(prev["Low"]), price * 0.95)

                breakout_picks[ticker] = {
                    "name": ticker,
                    "score": round(score_br, 2),
                    "entry_price": round(price, 4),
                    "stop_loss": round(stop_loss, 4),
                    "vol_ratio": round(vol_ratio, 2),
                    "rsi": round(float(curr["RSI"]), 1),
                    "trend_pct": round(trend_pct, 2),
                    "dollar_vol_avg20": round(float(curr["DollarVol_Avg20"]), 0),
                    "history": df["Close"].tail(30).round(4).tolist(),
                }

            # ====================================================
            # STRAT 2 : PULLBACK (REBOND SUR SMA50)
            # ====================================================
            sma50 = curr["SMA_50"]
            trend_strength = (price - curr["SMA_200"]) / curr["SMA_200"]

            near_sma50 = (
                not pd.isna(sma50)
                and abs((price - sma50) / sma50) <= 0.03  # +/- 3%
            )

            if (
                trend_strength > 0.05
                and near_sma50
                and curr["RSI"] < 60
            ):
                score_pb = pullback_score(curr)
                stop_loss = sma50 * 0.97  # 3 % sous la SMA50

                pullback_picks[ticker] = {
                    "name": ticker,
                    "score": round(score_pb, 2),
                    "entry_price": round(price, 4),
                    "stop_loss": round(stop_loss, 4),
                    "rsi": round(float(curr["RSI"]), 1),
                    "trend_pct": round(trend_strength * 100.0, 2),
                    "dollar_vol_avg20": round(float(curr["DollarVol_Avg20"]), 0),
                    "history": df["Close"].tail(30).round(4).tolist(),
                }

        except Exception as e:
            logger.warning(f"Erreur sur {ticker}: {e}")
            continue

    breakout_sorted = dict(
        sorted(breakout_picks.items(), key=lambda x: x[1]["score"], reverse=True)
    )
    pullback_sorted = dict(
        sorted(pullback_picks.items(), key=lambda x: x[1]["score"], reverse=True)
    )

    logger.info(
        f"{len(breakout_sorted)} signaux breakout et {len(pullback_sorted)} signaux pullback retenus."
    )
    return pullback_sorted, breakout_sorted


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)

    pullback_data, breakout_data = analyze_market()
    today = pd.Timestamp.now().strftime("%d/%m/%Y")

    result_pullback = {
        "date_mise_a_jour": today,
        "params": {
            "min_dollar_vol": MIN_DOLLAR_VOL,
            "min_candles": MIN_CANDLES,
        },
        "picks": pullback_data,
    }
    result_breakout = {
        "date_mise_a_jour": today,
        "params": {
            "min_dollar_vol": MIN_DOLLAR_VOL,
            "min_candles": MIN_CANDLES,
        },
        "picks": breakout_data,
    }

    with open(PULLBACK_FILE, "w") as f:
        json.dump(result_pullback, f, indent=4)

    with open(BREAKOUT_FILE, "w") as f:
        json.dump(result_breakout, f, indent=4)

    logger.info("Fichiers S&P 500 (pullback & breakout) sauvegardés.")

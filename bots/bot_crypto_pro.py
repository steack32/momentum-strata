import ccxt
import pandas as pd
import json
import time
import requests
import logging
from typing import Dict, Tuple

# =========================
# CONFIGURATION "HAUTE SENSIBILITÉ" + FALLBACK
# =========================

STABLECOINS = ["USDT", "USDC", "DAI", "FDUSD", "TUSA", "USDD", "PYUSD", "USDP", "EURI", "USDE", "BUSD", "USDS"]

# CRITÈRES ASSOUPLIS
MIN_CANDLES = 90               # On accepte les cryptos récentes (3 mois)
MIN_DOLLAR_VOL = 1_000_000     # 1M$ de volume journalier moyen (20j)
SLEEP_BETWEEN_CALLS = 0.2      # On ralentit un peu pour éviter le ban API

# Fallback : combien d'actifs max proposer si aucun signal strict ?
FALLBACK_MAX_BREAKOUT = 10
FALLBACK_MAX_PULLBACK = 10

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
    if max_val == min_val:
        return 0.0
    x = (value - min_val) / (max_val - min_val)
    if clip:
        x = max(0.0, min(1.0, x))
    return x

def get_top_cryptos(limit: int = 150):
    """
    Récupère le top market cap sur CoinGecko, filtre les stablecoins et quelques wrappers.
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
            if sym in STABLECOINS:
                continue
            if sym.startswith("W") and sym in ["WBTC", "WETH", "WBNB"]:
                continue
            if "STETH" in sym:
                continue

            symbols.append(sym)

        return symbols[:limit]
    except Exception as e:
        logger.warning(f"Erreur CoinGecko: {e}. Fallback liste réduite.")
        return ["BTC", "ETH", "SOL", "BNB", "PEPE", "DOGE", "RNDR", "FET", "INJ", "SUI", "SEI", "TIA"]

def fetch_ohlcv(symbol: str) -> pd.DataFrame | None:
    """
    Récupère OHLCV daily sur Binance ou Gate, vérifie que la dernière bougie n'est pas trop vieille.
    """
    pair = f"{symbol}/USDT"

    for exchange, name in [(exchange_binance, "Binance"), (exchange_gate, "Gate.io")]:
        try:
            ohlcv = exchange.fetch_ohlcv(pair, timeframe="1d", limit=200)
            if not ohlcv:
                continue

            df = pd.DataFrame(ohlcv, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])

            last_timestamp = df.iloc[-1]["timestamp"]
            current_timestamp = int(time.time() * 1000)

            # Si la dernière bougie a plus de 48h, on considère l'actif comme mort / delisté
            if (current_timestamp - last_timestamp) > 172800000:
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
    # SMA "long terme" : 200 si possible, sinon 90 pour les jeunes cryptos
    if len(df) >= 200:
        df["SMA_200"] = calculate_sma(df["Close"], 200)
    else:
        df["SMA_200"] = calculate_sma(df["Close"], 90)

    df["EMA_13"] = calculate_ema(df["Close"], 13)
    df["EMA_21"] = calculate_ema(df["Close"], 21)
    df["EMA_50"] = calculate_ema(df["Close"], 50)
    df["RSI"] = calculate_rsi(df["Close"], 14)
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
    # Score plus permissif sur la tendance
    trend_score = normalize(trend_pct, 0.0, 0.5)
    # Volume : on valorise dès 1.2x
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
    ema13 = curr["EMA_13"]
    ema50 = curr["EMA_50"]
    rsi = curr["RSI"]

    trend_strength = (price - sma200) / sma200

    # On cherche un prix qui est SOUS l'EMA 13 (Repli) mais pas trop loin de l'EMA 50
    dist_ema50 = (price - ema50) / ema50

    # Position score : 100% si on est pile sur l'EMA 50, diminue si on s'éloigne
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

    # Candidats pour fallback si 0 signaux stricts
    fallback_breakout_candidates = []
    fallback_pullback_candidates = []

    logger.info(f"🚀 Analyse V3 (Haute Sensibilité) sur {len(SYMBOLS)} actifs...")

    for i, symbol in enumerate(SYMBOLS):
        if i % 10 == 0:
            time.sleep(SLEEP_BETWEEN_CALLS)

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
                # filtre stablecoin
                continue

            vol_usd = curr.get("DollarVol_Avg20", 0)
            # Filtre liquidité
            if pd.isna(vol_usd) or vol_usd < MIN_DOLLAR_VOL:
                continue

            trend_strength = (price - curr["SMA_200"]) / curr["SMA_200"]

            # =========================
            # STRAT 1 : PHOENIX (BREAKOUT)
            # =========================
            vol_ratio = curr["Volume"] / curr["Vol_Avg"] if curr["Vol_Avg"] > 0 else 0
            is_green = (price > curr["Open"]) or (price > prev["Close"])
            in_trend = price > curr["SMA_200"]

            phoenix_score_val = phoenix_breakout_score(curr, prev)

            # Candidat fallback : on garde les valeurs bien classées même si elles ne passent pas le strict filtre
            if in_trend and vol_ratio > 0.8 and phoenix_score_val >= 40:
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

            # Conditions strictes (comme avant, légèrement assouplies)
            if in_trend and is_green and (vol_ratio > 1.2):
                score = phoenix_score_val
                stop_loss = min(prev["Low"], price * 0.90)

                breakout_picks[symbol] = {
                    "name": symbol,
                    "score": round(score, 2),
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "vol_ratio": round(vol_ratio, 2),
                    "rsi": round(curr["RSI"], 1),
                    "trend_pct": round(trend_strength * 100, 2),
                    "dollar_vol_avg20": round(vol_usd, 0),
                    "history": df["Close"].tail(30).round(6).tolist()
                }

            # =========================
            # STRAT 2 : PULLBACK (REBOND)
            # =========================
            is_pulling_back = (price < curr["EMA_13"])
            is_holding_support = (price > curr["EMA_50"] * 0.98)

            pullback_score_val = pullback_score(curr)

            # Candidat fallback pullback
            if trend_strength > -0.05 and curr["RSI"] < 70 and pullback_score_val >= 40:
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

            # Conditions strictes (comme avant)
            if (trend_strength > 0) and is_pulling_back and is_holding_support and (curr["RSI"] < 60):
                score_pb = pullback_score_val
                stop_loss_pb = curr["EMA_50"] * 0.90

                pullback_picks[symbol] = {
                    "name": symbol,
                    "score": round(score_pb, 2),
                    "entry_price": price,
                    "stop_loss": stop_loss_pb,
                    "rsi": round(curr["RSI"], 1),
                    "trend_pct": round(trend_strength * 100, 2),
                    "dollar_vol_avg20": round(vol_usd, 0),
                    "history": df["Close"].tail(30).round(6).tolist()
                }

        except Exception as e:
            # On logge en debug éventuellement si tu veux creuser plus tard
            # logger.debug(f"Erreur sur {symbol}: {e}")
            continue

    # ================
    # TRI & FALLBACK
    # ================

    # Si aucun breakout strict, on prend les meilleurs candidats fallback
    if not breakout_picks and fallback_breakout_candidates:
        logger.info("⚠️ Aucun breakout crypto strict trouvé. Utilisation du fallback (top breakouts relatifs).")
        fallback_breakout_candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in fallback_breakout_candidates[:FALLBACK_MAX_BREAKOUT]:
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

    # Si aucun pullback strict, on prend les meilleurs candidats fallback
    if not pullback_picks and fallback_pullback_candidates:
        logger.info("⚠️ Aucun pullback crypto strict trouvé. Utilisation du fallback (top pullbacks relatifs).")
        fallback_pullback_candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in fallback_pullback_candidates[:FALLBACK_MAX_PULLBACK]:
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

    logger.info(f"✅ RÉSULTAT FINAL : {len(breakout_sorted)} Breakouts | {len(pullback_sorted)} Pullbacks")
    return pullback_sorted, breakout_sorted

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    pullback_data, breakout_data = analyze_market()
    today = pd.Timestamp.now().strftime("%d/%m/%Y")

    with open("data/crypto_pullback_pro.json", "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": pullback_data}, f, indent=4)
    with open("data/crypto_breakout_pro.json", "w") as f:
        json.dump({"date_mise_a_jour": today, "picks": breakout_data}, f, indent=4)

    print("💾 Fichiers Crypto sauvegardés.")

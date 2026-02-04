# bots/generate_backtest_signals.py
# Génération des signaux de backtest sur 2 ans

import os
import logging
from typing import Dict, List

import pandas as pd

from config import (
    LOG_PATH_BACKTEST,
    DATA_DIR,
    SP500_MIN_DOLLAR_VOL,
    CRYPTO_MIN_CANDLES,
    CRYPTO_MIN_DOLLAR_VOL,
    SLIPPAGE_ENTRY,
    SLIPPAGE_EXIT,
)
from json_utils import save_json
import bot_sp500_pro as sp500
import bot_crypto_pro as crypto


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("backtest_signals")


def build_entry(
    universe: str,
    strategy: str,
    ticker: str,
    date_iso: str,
    entry_price: float,
    stop_loss: float,
) -> Dict:
    """Construit une entrée de log pour un signal."""
    _id = f"{universe}_{strategy}_{ticker}_{date_iso}"

    return {
        "id": _id,
        "date_signal": date_iso,
        "ticker": ticker,
        "universe": universe,
        "strategy": strategy,
        "initial_data": {
            "close_j": float(entry_price),
            "stop_loss_technical": float(stop_loss),
        },
        "trade_status": "PENDING",
        "execution": {
            "entry_price": None,
            "entry_date": None,
            "exit_price": None,
            "exit_date": None,
            "exit_reason": None,
            "breakeven_activated": False,
            "slippage": {
                "entry_factor": SLIPPAGE_ENTRY,
                "exit_factor": SLIPPAGE_EXIT,
            },
        },
    }


def generate_sp500_signals() -> List[Dict]:
    """
    Rejoue la logique de bot_sp500_pro sur ~2 ans pour chaque ticker.
    """
    entries: List[Dict] = []

    tickers_map = sp500.get_sp500_tickers()
    logger.info(f"[SP500] Nombre de tickers : {len(tickers_map)}")

    for i, (ticker, company_name) in enumerate(tickers_map.items(), 1):
        if i % 20 == 0:
            logger.info(f"[SP500] {i}/{len(tickers_map)} tickers traités...")

        df = sp500.fetch_ohlcv_yf(ticker)
        if df is None or df.empty:
            continue

        try:
            df = sp500.compute_indicators(df)
            df = df.dropna(
                subset=["SMA_200", "SMA_50", "RSI", "Vol_Avg", "DollarVol_Avg20"]
            )
            if df.empty:
                continue

            for idx in range(1, len(df)):
                curr = df.iloc[idx]
                prev = df.iloc[idx - 1]

                if not sp500.liquidity_filter(curr):
                    continue

                price = float(curr["Close"])
                if price <= 0:
                    continue

                date_iso = df.index[idx].date().isoformat()

                # ========= PHOENIX (breakout) =========
                vol_ratio = (
                    curr["Volume"] / curr["Vol_Avg"]
                    if curr["Vol_Avg"] > 0
                    else 0.0
                )
                if (
                    price > curr["SMA_200"]
                    and price > float(prev["Close"])
                    and vol_ratio > 2.0
                ):
                    stop_loss = min(float(prev["Low"]), price * 0.95)
                    entry = build_entry(
                        universe="sp500",
                        strategy="phoenix",
                        ticker=ticker,
                        date_iso=date_iso,
                        entry_price=price,
                        stop_loss=stop_loss,
                    )
                    entries.append(entry)

                # ========= PULLBACK =========
                sma50 = curr["SMA_50"]
                if pd.isna(sma50):
                    continue

                trend = (price - curr["SMA_200"]) / curr["SMA_200"]
                near_sma50 = abs((price - sma50) / sma50) <= 0.03

                if trend > 0.05 and near_sma50 and curr["RSI"] < 60:
                    stop_loss_pb = float(sma50) * 0.95
                    entry_pb = build_entry(
                        universe="sp500",
                        strategy="pullback",
                        ticker=ticker,
                        date_iso=date_iso,
                        entry_price=price,
                        stop_loss=stop_loss_pb,
                    )
                    entries.append(entry_pb)

        except Exception as e:
            logger.warning(f"[SP500] Erreur sur {ticker}: {e}")
            continue

    logger.info(f"[SP500] Total signaux générés : {len(entries)}")
    return entries


def fetch_ohlcv_crypto_history(symbol: str, limit: int = 730) -> pd.DataFrame | None:
    """
    Historique daily sur Binance pour le backtest.
    """
    pair = f"{symbol}/USDT"

    try:
        ohlcv = crypto.exchange_binance.fetch_ohlcv(
            pair, timeframe="1d", limit=limit
        )
        if not ohlcv:
            return None

        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "Open", "High", "Low", "Close", "Volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        logger.warning(f"[CRYPTO] Erreur fetch OHLCV {symbol}/USDT: {e}")
        return None


def generate_crypto_signals() -> List[Dict]:
    """
    Rejoue la logique de bot_crypto_pro sur l'historique.
    """
    entries: List[Dict] = []

    symbols = crypto.get_top_cryptos(150)
    logger.info(f"[CRYPTO] Nombre de symboles : {len(symbols)}")

    for i, symbol in enumerate(symbols, 1):
        if i % 10 == 0:
            logger.info(f"[CRYPTO] {i}/{len(symbols)} actifs traités...")

        df = fetch_ohlcv_crypto_history(symbol, limit=730)
        if df is None or df.empty:
            continue

        if len(df) < CRYPTO_MIN_CANDLES:
            continue

        try:
            df = crypto.compute_indicators(df)
            df = df.dropna(
                subset=[
                    "SMA_200",
                    "RSI",
                    "Vol_Avg",
                    "DollarVol_Avg20",
                    "EMA_13",
                    "EMA_21",
                    "EMA_50",
                ]
            )
            if df.empty:
                continue

            for idx in range(1, len(df)):
                curr = df.iloc[idx]
                prev = df.iloc[idx - 1]
                price = float(curr["Close"])

                if pd.isna(curr["SMA_200"]) or price <= 0:
                    continue

                if 0.98 <= price <= 1.02:
                    continue

                vol_usd = curr.get("DollarVol_Avg20", 0.0)
                if pd.isna(vol_usd) or vol_usd < CRYPTO_MIN_DOLLAR_VOL:
                    continue

                trend_strength = (price - curr["SMA_200"]) / curr["SMA_200"]
                vol_ratio = (
                    curr["Volume"] / curr["Vol_Avg"]
                    if curr["Vol_Avg"] > 0
                    else 0.0
                )
                is_green = (price > curr["Open"]) or (price > prev["Close"])
                in_trend = price > curr["SMA_200"]

                date_iso = df.index[idx].date().isoformat()

                # ========= PHOENIX (breakout strict) =========
                if in_trend and is_green and (vol_ratio > 1.2):
                    stop_loss = min(float(prev["Low"]), price * 0.90)
                    entry = build_entry(
                        universe="crypto",
                        strategy="phoenix",
                        ticker=symbol,
                        date_iso=date_iso,
                        entry_price=price,
                        stop_loss=stop_loss,
                    )
                    entries.append(entry)

                # ========= PULLBACK (strict) =========
                is_pulling_back = price < curr["EMA_13"]
                is_holding_support = price > curr["EMA_50"] * 0.98

                if (
                    trend_strength > 0
                    and is_pulling_back
                    and is_holding_support
                    and curr["RSI"] < 60
                ):
                    stop_loss_pb = float(curr["EMA_50"]) * 0.90
                    entry_pb = build_entry(
                        universe="crypto",
                        strategy="pullback",
                        ticker=symbol,
                        date_iso=date_iso,
                        entry_price=price,
                        stop_loss=stop_loss_pb,
                    )
                    entries.append(entry_pb)

        except Exception as e:
            logger.warning(f"[CRYPTO] Erreur sur {symbol}: {e}")
            continue

    logger.info(f"[CRYPTO] Total signaux générés : {len(entries)}")
    return entries


def main():
    sp500_entries = generate_sp500_signals()
    crypto_entries = generate_crypto_signals()

    all_entries = sp500_entries + crypto_entries

    # Tri propre pour avoir un fichier stable
    all_entries_sorted = sorted(
        all_entries,
        key=lambda e: (
            e.get("date_signal", ""),
            e.get("universe", ""),
            e.get("strategy", ""),
            e.get("ticker", ""),
        ),
    )

    os.makedirs(DATA_DIR, exist_ok=True)
    save_json(all_entries_sorted, LOG_PATH_BACKTEST)

    logger.info(
        f"[OK] Backtest log généré : {LOG_PATH_BACKTEST} "
        f"({len(all_entries_sorted)} signaux)"
    )


if __name__ == "__main__":
    main()

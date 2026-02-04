# bots/perf_summary.py
# Calcul des performances en temps réel (signaux live)

import logging
from typing import Dict, Optional

import pandas as pd
import yfinance as yf
import ccxt

from config import LOG_PATH, OUT_PATH, STRATEGY_KEYS
from json_utils import load_signals_log, save_signals_log, save_json
from trade_simulator import simulate_trade, build_equity_curve, calculate_performance_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("perf_summary")

# Caches pour éviter de refetch en boucle
_sp500_cache: Dict[str, pd.DataFrame] = {}
_crypto_cache: Dict[str, pd.DataFrame] = {}

exchange_binance = ccxt.binance({"enableRateLimit": True})


def get_sp500_history(ticker: str) -> Optional[pd.DataFrame]:
    """Récupère l'historique OHLC d'une action S&P 500."""
    if ticker in _sp500_cache:
        return _sp500_cache[ticker]

    try:
        df = yf.download(ticker, period="2y", interval="1d", auto_adjust=False, progress=False)
        if df.empty:
            return None

        df = df[["Open", "High", "Low", "Close"]].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        _sp500_cache[ticker] = df
        return df
    except Exception as e:
        logger.warning(f"Erreur yfinance pour {ticker}: {e}")
        return None


def get_crypto_history(symbol: str) -> Optional[pd.DataFrame]:
    """Récupère l'historique OHLC d'une crypto via Binance."""
    if symbol in _crypto_cache:
        return _crypto_cache[symbol]

    pair = f"{symbol}/USDT"
    try:
        ohlcv = exchange_binance.fetch_ohlcv(pair, timeframe="1d", limit=200)
        if not ohlcv:
            return None

        df = pd.DataFrame(ohlcv, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df.index = df.index.tz_localize(None)
        df = df[["Open", "High", "Low", "Close"]]
        _crypto_cache[symbol] = df
        return df
    except Exception as e:
        logger.warning(f"Erreur ccxt pour {symbol}/USDT: {e}")
        return None


def main():
    signals = load_signals_log(LOG_PATH)
    if not signals:
        logger.info("Aucun signal dans le log. Rien à faire.")
        empty_summary = {
            "last_update": pd.Timestamp.utcnow().strftime("%Y-%m-%d"),
            **{key: {} for key in STRATEGY_KEYS},
            "equity_curve": {
                "global": {"dates": [], "equity_pct": []},
                **{key: {"dates": [], "equity_pct": []} for key in STRATEGY_KEYS},
            },
        }
        save_json(empty_summary, OUT_PATH)
        return

    # Groupes pour chaque stratégie
    groups = {key: {"R": [], "exit_reasons": [], "equity_trades": []} for key in STRATEGY_KEYS}

    updated_signals = []
    global_equity_trades = []

    for entry in signals:
        try:
            date_signal_str = entry.get("date_signal")
            universe = entry.get("universe")
            strategy = entry.get("strategy")
            ticker = entry.get("ticker")

            if not (date_signal_str and universe and strategy and ticker):
                updated_signals.append(entry)
                continue

            key = f"{universe}_{strategy}"
            if key not in groups:
                updated_signals.append(entry)
                continue

            initial_data = entry.get("initial_data", {})
            stop_loss_initial = float(initial_data.get("stop_loss_technical", 0.0))
            if stop_loss_initial <= 0:
                updated_signals.append(entry)
                continue

            date_signal = pd.to_datetime(date_signal_str)

            # Historique du sous-jacent
            if universe == "sp500":
                df = get_sp500_history(ticker)
            else:
                df = get_crypto_history(ticker)

            if df is None or df.empty:
                updated_signals.append(entry)
                continue

            sim = simulate_trade(df, date_signal, stop_loss_initial)
            if sim is None:
                updated_signals.append(entry)
                continue

            status = sim.get("status", "PENDING")

            exec_block = entry.get("execution", {}) or {}
            exec_block.update({
                "entry_price": sim.get("entry_price", exec_block.get("entry_price")),
                "entry_date": sim.get("entry_date", exec_block.get("entry_date")),
                "exit_price": sim.get("exit_price", exec_block.get("exit_price")),
                "exit_date": sim.get("exit_date", exec_block.get("exit_date")),
                "exit_reason": sim.get("exit_reason", exec_block.get("exit_reason")),
                "breakeven_activated": sim.get("breakeven_activated", exec_block.get("breakeven_activated", False)),
                "slippage": sim.get("slippage", exec_block.get("slippage")),
            })

            entry["execution"] = exec_block
            entry["trade_status"] = status

            if status == "CLOSED":
                R_val = sim.get("R")
                exit_reason = sim.get("exit_reason", "SL")
                perf_pct = sim.get("perf_pct")

                if R_val is not None:
                    groups[key]["R"].append(R_val)
                    groups[key]["exit_reasons"].append(exit_reason)

                if perf_pct is not None and exec_block.get("exit_date"):
                    trade_point = {
                        "exit_date": exec_block["exit_date"],
                        "perf_pct": float(perf_pct),
                    }
                    global_equity_trades.append(trade_point)
                    groups[key]["equity_trades"].append(trade_point)

            updated_signals.append(entry)

        except Exception as e:
            logger.warning(f"Erreur sur un signal {entry.get('id')}: {e}")
            updated_signals.append(entry)
            continue

    # Sauvegarde du log enrichi
    save_signals_log(updated_signals, LOG_PATH)

    # Construction du résumé
    summary = {
        "last_update": pd.Timestamp.utcnow().strftime("%Y-%m-%d"),
    }

    # Agrégation par stratégie
    for key, data in groups.items():
        summary[key] = calculate_performance_metrics(data["R"], data["exit_reasons"])

    # Construction des equity curves
    summary["equity_curve"] = {
        "global": build_equity_curve(global_equity_trades),
        **{key: build_equity_curve(groups[key]["equity_trades"]) for key in STRATEGY_KEYS},
    }

    save_json(summary, OUT_PATH)
    logger.info("Performance summary updated.")


if __name__ == "__main__":
    main()

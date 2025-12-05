# bots/perf_summary.py

import json
import os
from typing import Dict, Optional, Tuple

import pandas as pd
import yfinance as yf
import ccxt
import logging

LOG_PATH = "data/signals_log.json"
OUT_PATH = "data/performance_summary.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("perf_summary")

# caches pour éviter de refetch
_sp500_cache: Dict[str, pd.DataFrame] = {}
_crypto_cache: Dict[str, pd.DataFrame] = {}

exchange_binance = ccxt.binance({"enableRateLimit": True})


# =========================
# UTILITAIRES
# =========================

def load_signals_log():
    if not os.path.exists(LOG_PATH):
        return []
    try:
        with open(LOG_PATH, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_signals_log(log):
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


def save_perf_summary(summary: Dict):
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(summary, f, indent=2)


def get_sp500_history(ticker: str) -> Optional[pd.DataFrame]:
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


# =========================
# LOGIQUE DE TRADE
# =========================

def simulate_trade(
    df: pd.DataFrame,
    date_signal: pd.Timestamp,
    stop_loss_initial: float,
) -> Optional[Dict]:
    """
    Simule un trade Trader mode :
    - entrée à l'OPEN de la 1ère bougie > date_signal (J+1)
    - slippage entrée: *1.001
    - slippage sortie: *0.999
    - gestion du stop + breakeven + time stop J+10

    Retour:
      - dict avec status:
          * "PENDING"  -> pas encore de bougie J+1
          * "ACTIVE"   -> entrée faite, mais pas encore SL/BE/TIME
          * "CLOSED"   -> trade terminé (SL / BE / TIME)
    """
    if stop_loss_initial is None or stop_loss_initial <= 0:
        return None

    df = df.sort_index()

    # bougies strictement après la date du signal
    df_after = df[df.index.date > date_signal.date()]
    if df_after.empty:
        # pas encore de J+1 → trade pending
        return {"status": "PENDING"}

    # bougie d'entrée = 1ère bougie après date_signal
    entry_idx = df_after.index[0]
    entry_row = df_after.loc[entry_idx]
    entry_open_raw = float(entry_row["Open"])

    if entry_open_raw <= 0 or stop_loss_initial >= entry_open_raw:
        # stop incohérent ou prix nul
        return None

    # Prix simulés (friction)
    entry_price = entry_open_raw * 1.001  # frais+slippage
    risk_per_unit = entry_price - stop_loss_initial
    if risk_per_unit <= 0:
        return None

    # 1R en espace "prix brut" (pour la condition BE)
    risk_raw = entry_open_raw - stop_loss_initial
    be_trigger_raw = entry_open_raw + risk_raw

    current_stop = stop_loss_initial  # en prix brut
    breakeven_activated = False

    exit_idx = None
    exit_raw_price = None
    exit_reason = None  # "SL", "BE", "TIME"

    # Fenêtre de trade : jusqu'à 10 bougies après l'entrée
    trade_df = df_after.loc[entry_idx:]
    rows = list(trade_df.iloc[:10].iterrows())
    if not rows:
        # On a une bougie J+1 dans df_after mais par sécurité
        return {"status": "ACTIVE", "entry_price": entry_price, "entry_date": entry_idx.date().isoformat()}

    for i, (idx, row) in enumerate(rows, start=1):
        o = float(row["Open"])
        h = float(row["High"])
        l = float(row["Low"])
        c = float(row["Close"])

        # 1. GAP sous le stop actuel
        if o <= current_stop:
            exit_idx = idx
            exit_raw_price = o
            exit_reason = "BE" if breakeven_activated and current_stop >= entry_open_raw else "SL"
            break

        # 2. Stop intraday
        if l <= current_stop:
            exit_idx = idx
            exit_raw_price = current_stop
            exit_reason = "BE" if breakeven_activated and current_stop >= entry_open_raw else "SL"
            break

        # 3. Breakeven (fin de journée) si pas encore sécurisé
        if (not breakeven_activated) and (h >= be_trigger_raw):
            breakeven_activated = True
            current_stop = entry_open_raw  # stop à l'entry brut

        # 4. Time stop J+10
        is_last_bar = (i == len(rows))
        if is_last_bar and i >= 10:
            exit_idx = idx
            exit_raw_price = c
            exit_reason = "TIME"
            break

    # Aucun exit et < 10 bougies → trade encore actif
    if exit_idx is None:
        return {
            "status": "ACTIVE",
            "entry_price": entry_price,
            "entry_date": entry_idx.date().isoformat(),
            "breakeven_activated": breakeven_activated,
        }

    # Sortie simulée avec friction
    exit_price = exit_raw_price * 0.999

    perf_pct = (exit_price / entry_price - 1.0) * 100.0
    R = (exit_price - entry_price) / risk_per_unit

    return {
        "status": "CLOSED",
        "entry_price": entry_price,
        "entry_date": entry_idx.date().isoformat(),
        "exit_price": exit_price,
        "exit_date": exit_idx.date().isoformat(),
        "exit_reason": exit_reason,  # "SL", "BE" ou "TIME"
        "breakeven_activated": breakeven_activated,
        "perf_pct": perf_pct,
        "R": R,
        "slippage": {
            "entry_factor": 1.001,
            "exit_factor": 0.999,
        },
    }


# =========================
# MAIN + AGRÉGATION
# =========================

def main():
    signals = load_signals_log()
    if not signals:
        logger.info("Aucun signal dans le log. Rien à faire.")
        save_perf_summary(
            {
                "last_update": pd.Timestamp.utcnow().strftime("%Y-%m-%d"),
                "sp500_phoenix": {},
                "sp500_pullback": {},
                "crypto_phoenix": {},
                "crypto_pullback": {},
            }
        )
        return

    # 4 groupes principaux
    groups = {
        "sp500_phoenix": {"R": [], "exit_reasons": []},
        "sp500_pullback": {"R": [], "exit_reasons": []},
        "crypto_phoenix": {"R": [], "exit_reasons": []},
        "crypto_pullback": {"R": [], "exit_reasons": []},
    }

    # On mettra à jour signals_log avec trade_status / execution
    updated_signals = []

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

            # Récupération historique
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

            # Mise à jour du bloc execution
            exec_block = entry.get("execution", {}) or {}
            exec_block.update(
                {
                    "entry_price": sim.get("entry_price", exec_block.get("entry_price")),
                    "entry_date": sim.get("entry_date", exec_block.get("entry_date")),
                    "exit_price": sim.get("exit_price", exec_block.get("exit_price")),
                    "exit_date": sim.get("exit_date", exec_block.get("exit_date")),
                    "exit_reason": sim.get("exit_reason", exec_block.get("exit_reason")),
                    "breakeven_activated": sim.get(
                        "breakeven_activated",
                        exec_block.get("breakeven_activated", False),
                    ),
                    "slippage": sim.get("slippage", exec_block.get("slippage")),
                }
            )

            entry["execution"] = exec_block
            entry["trade_status"] = status

            # Si le trade est fermé, on l'intègre aux stats
            if status == "CLOSED":
                R_val = sim.get("R")
                exit_reason = sim.get("exit_reason", "SL")
                if R_val is not None:
                    groups[key]["R"].append(R_val)
                    groups[key]["exit_reasons"].append(exit_reason)

            updated_signals.append(entry)

        except Exception as e:
            logger.warning(f"Erreur sur un signal {entry.get('id')}: {e}")
            updated_signals.append(entry)
            continue

    # Sauvegarde du log mis à jour
    save_signals_log(updated_signals)

    # Agrégation des métriques
    summary = {
        "last_update": pd.Timestamp.utcnow().strftime("%Y-%m-%d"),
    }

    for key, data in groups.items():
        R_list = data["R"]
        exit_reasons = data["exit_reasons"]
        n = len(R_list)

        if n == 0:
            summary[key] = {
                "nb_trades": 0,
                "avg_R": 0.0,
                "winrate": 0.0,
                "breakeven_rate": 0.0,
                "expectancy_R": 0.0,
                "avg_win_R": 0.0,
                "avg_loss_R": 0.0,
            }
            continue

        # BE = trades sortis avec exit_reason == "BE"
        be_count = sum(1 for r in exit_reasons if r == "BE")
        be_rate = be_count / n * 100.0

        # On sépare wins / losses (hors BE pour le calcul win/loss)
        R_and_reason = list(zip(R_list, exit_reasons))

        wins = [R for R, reason in R_and_reason if R > 0 and reason != "BE"]
        losses = [R for R, reason in R_and_reason if R < 0 and reason != "BE"]

        winrate = (len(wins) / n * 100.0) if n > 0 else 0.0
        lossrate = (len(losses) / n * 100.0) if n > 0 else 0.0

        avg_win_R = sum(wins) / len(wins) if wins else 0.0
        avg_loss_R_abs = -sum(losses) / len(losses) if losses else 0.0  # valeur positive

        # Expectancy en R selon la formule
        expectancy_R = (winrate / 100.0) * avg_win_R - (lossrate / 100.0) * avg_loss_R_abs

        avg_R_global = sum(R_list) / n

        summary[key] = {
            "nb_trades": n,
            "avg_R": round(avg_R_global, 3),
            "winrate": round(winrate, 1),
            "breakeven_rate": round(be_rate, 1),
            "expectancy_R": round(expectancy_R, 3),
            "avg_win_R": round(avg_win_R, 3),
            "avg_loss_R": round(avg_loss_R_abs, 3),
        }

    save_perf_summary(summary)
    logger.info("Performance summary updated.")
    logger.info(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

# bots/trade_simulator.py
# Simulation de trades et calcul de performance

from typing import Dict, List, Optional
import pandas as pd

from config import SLIPPAGE_ENTRY, SLIPPAGE_EXIT, MAX_BARS_IN_TRADE


def simulate_trade(
    df: pd.DataFrame,
    date_signal: pd.Timestamp,
    stop_loss_initial: float
) -> Optional[Dict]:
    """
    Simule un trade en mode Trader V2.

    Règles :
    - Entrée à l'OPEN de la 1ère bougie > date_signal (J+1), avec slippage/frais
    - Stop Loss initial = stop_loss_initial (issu du signal)
    - Breakeven : dès que High >= Entry + 1R (en brut), stop déplacé à l'entry brut
    - Time stop : close de la 10e bougie après l'entrée si aucun stop touché
    - Sortie avec slippage/frais

    Args:
        df: DataFrame OHLC du sous-jacent
        date_signal: Date du signal
        stop_loss_initial: Prix du stop loss initial

    Returns:
        Dict avec le résultat du trade ou None si invalide
    """
    if stop_loss_initial is None or stop_loss_initial <= 0:
        return None

    df = df.sort_index()

    # Bougies strictement après la date du signal
    df_after = df[df.index.date > date_signal.date()]
    if df_after.empty:
        return {"status": "PENDING"}

    # Bougie d'entrée = première bougie après date_signal
    entry_idx = df_after.index[0]
    entry_row = df_after.loc[entry_idx]
    entry_open_raw = float(entry_row["Open"])

    # Entrée invalide si open <= 0 ou stop au-dessus de l'open
    if entry_open_raw <= 0 or stop_loss_initial >= entry_open_raw:
        return None

    # Prix simulés avec slippage/frais
    entry_price = entry_open_raw * SLIPPAGE_ENTRY
    risk_per_unit = entry_price - stop_loss_initial
    if risk_per_unit <= 0:
        return None

    # 1R en brut pour déclencher le BE
    risk_raw = entry_open_raw - stop_loss_initial
    be_trigger_raw = entry_open_raw + risk_raw

    current_stop = stop_loss_initial
    breakeven_activated = False

    exit_idx = None
    exit_raw_price = None
    exit_reason = None

    trade_df = df_after.loc[entry_idx:]
    rows = list(trade_df.iloc[:MAX_BARS_IN_TRADE].iterrows())

    if not rows:
        return {
            "status": "ACTIVE",
            "entry_price": entry_price,
            "entry_date": entry_idx.date().isoformat(),
            "breakeven_activated": breakeven_activated,
        }

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

        # 3. Passage au breakeven si +1R atteint (en brut)
        if (not breakeven_activated) and (h >= be_trigger_raw):
            breakeven_activated = True
            current_stop = entry_open_raw

        # 4. Time stop à la dernière bougie
        is_last_bar = (i == len(rows))
        if is_last_bar and i >= MAX_BARS_IN_TRADE:
            exit_idx = idx
            exit_raw_price = c
            exit_reason = "TIME"
            break

    # Si aucun exit trouvé et moins de MAX_BARS_IN_TRADE barres -> trade toujours actif
    if exit_idx is None:
        return {
            "status": "ACTIVE",
            "entry_price": entry_price,
            "entry_date": entry_idx.date().isoformat(),
            "breakeven_activated": breakeven_activated,
        }

    # Sortie avec slippage / frais
    exit_price = exit_raw_price * SLIPPAGE_EXIT

    perf_pct = (exit_price / entry_price - 1.0) * 100.0
    R = (exit_price - entry_price) / risk_per_unit

    return {
        "status": "CLOSED",
        "entry_price": entry_price,
        "entry_date": entry_idx.date().isoformat(),
        "exit_price": exit_price,
        "exit_date": exit_idx.date().isoformat(),
        "exit_reason": exit_reason,
        "breakeven_activated": breakeven_activated,
        "perf_pct": perf_pct,
        "R": R,
        "slippage": {
            "entry_factor": SLIPPAGE_ENTRY,
            "exit_factor": SLIPPAGE_EXIT,
        },
    }


def build_equity_curve(trades: List[Dict]) -> Dict:
    """
    Construit une courbe d'équité à partir d'une liste de trades.

    Args:
        trades: Liste de dicts avec "exit_date" et "perf_pct"

    Returns:
        Dict avec "dates" et "equity_pct"
    """
    if not trades:
        return {"dates": [], "equity_pct": []}

    df_eq = pd.DataFrame(trades)
    df_eq["exit_date"] = pd.to_datetime(df_eq["exit_date"])
    df_eq = df_eq.sort_values("exit_date")
    df_eq["date"] = df_eq["exit_date"].dt.date

    daily = df_eq.groupby("date")["perf_pct"].sum().reset_index()
    daily["equity_pct"] = daily["perf_pct"].cumsum()

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in daily["date"]],
        "equity_pct": [round(v, 2) for v in daily["equity_pct"]],
    }


def calculate_performance_metrics(R_list: List[float], exit_reasons: List[str]) -> Dict:
    """
    Calcule les métriques de performance à partir d'une liste de R.

    Args:
        R_list: Liste des R de chaque trade
        exit_reasons: Liste des raisons de sortie ("SL", "BE", "TIME")

    Returns:
        Dict avec les métriques de performance
    """
    n = len(R_list)

    if n == 0:
        return {
            "nb_trades": 0,
            "avg_R": 0.0,
            "winrate": 0.0,
            "breakeven_rate": 0.0,
            "expectancy_R": 0.0,
            "avg_win_R": 0.0,
            "avg_loss_R": 0.0,
        }

    be_count = sum(1 for r in exit_reasons if r == "BE")
    be_rate = be_count / n * 100.0

    R_and_reason = list(zip(R_list, exit_reasons))
    wins = [R for R, reason in R_and_reason if R > 0 and reason != "BE"]
    losses = [R for R, reason in R_and_reason if R < 0 and reason != "BE"]

    winrate = (len(wins) / n * 100.0) if n > 0 else 0.0
    lossrate = (len(losses) / n * 100.0) if n > 0 else 0.0

    avg_win_R = sum(wins) / len(wins) if wins else 0.0
    avg_loss_R_abs = -sum(losses) / len(losses) if losses else 0.0

    expectancy_R = (winrate / 100.0) * avg_win_R - (lossrate / 100.0) * avg_loss_R_abs
    avg_R_global = sum(R_list) / n

    return {
        "nb_trades": n,
        "avg_R": round(avg_R_global, 3),
        "winrate": round(winrate, 1),
        "breakeven_rate": round(be_rate, 1),
        "expectancy_R": round(expectancy_R, 3),
        "avg_win_R": round(avg_win_R, 3),
        "avg_loss_R": round(avg_loss_R_abs, 3),
    }

# bots/log_signals.py

import json
import os
import pandas as pd

LOG_PATH = "data/signals_log.json"

SOURCES = [
    ("data/sp500_breakout_pro.json", "sp500", "phoenix"),
    ("data/sp500_pullback_pro.json", "sp500", "pullback"),
    ("data/crypto_breakout_pro.json", "crypto", "phoenix"),
    ("data/crypto_pullback_pro.json", "crypto", "pullback"),
]


def load_json_safe(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


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
    # tri pour garder un truc propre
    log_sorted = sorted(
        log,
        key=lambda e: (
            e.get("date_signal", ""),
            e.get("universe", ""),
            e.get("strategy", ""),
            e.get("ticker", ""),
        ),
    )
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(log_sorted, f, indent=2)


def main():
    log = load_signals_log()

    existing_ids = {entry.get("id") for entry in log if "id" in entry}
    new_entries = 0

    for path, universe, strategy in SOURCES:
        data = load_json_safe(path)
        if not data:
            continue

        date_str = data.get("date_mise_a_jour")  # ex "05/12/2025"
        if not date_str:
            continue

        try:
            ts = pd.to_datetime(date_str, dayfirst=True)
            date_iso = ts.strftime("%Y-%m-%d")
        except Exception:
            continue

        picks = data.get("picks", {})
        if not isinstance(picks, dict):
            continue

        for ticker, info in picks.items():
            close_j = info.get("entry_price")
            stop_loss = info.get("stop_loss")
            if close_j is None or stop_loss is None:
                continue

            # ID unique
            _id = f"{universe}_{strategy}_{ticker}_{date_iso}"
            if _id in existing_ids:
                continue

            entry = {
                "id": _id,
                "date_signal": date_iso,
                "ticker": ticker,
                "universe": universe,
                "strategy": strategy,
                "initial_data": {
                    "close_j": float(close_j),
                    "stop_loss_technical": float(stop_loss),
                },
                "trade_status": "PENDING",
                "execution": {
                    "entry_price": None,
                    "entry_date": None,
                    "exit_price": None,
                    "exit_date": None,
                    "exit_reason": None,  # "SL", "BE", "TIME"
                    "breakeven_activated": False,
                    "slippage": {
                        "entry_factor": 1.001,
                        "exit_factor": 0.999,
                    },
                },
            }

            log.append(entry)
            existing_ids.add(_id)
            new_entries += 1

    save_signals_log(log)
    print(f"Signals log updated. New entries: {new_entries}")


if __name__ == "__main__":
    main()

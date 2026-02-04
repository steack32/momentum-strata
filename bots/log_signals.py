# bots/log_signals.py
# Enregistrement des signaux quotidiens dans le log

import pandas as pd

from config import LOG_PATH, SIGNAL_SOURCES, SLIPPAGE_ENTRY, SLIPPAGE_EXIT
from json_utils import load_json_safe, load_signals_log, save_signals_log


def main():
    log = load_signals_log(LOG_PATH)

    existing_ids = {entry.get("id") for entry in log if "id" in entry}
    new_entries = 0

    for path, universe, strategy in SIGNAL_SOURCES:
        data = load_json_safe(path)
        if not data:
            continue

        date_str = data.get("date_mise_a_jour")
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
                    "exit_reason": None,
                    "breakeven_activated": False,
                    "slippage": {
                        "entry_factor": SLIPPAGE_ENTRY,
                        "exit_factor": SLIPPAGE_EXIT,
                    },
                },
            }

            log.append(entry)
            existing_ids.add(_id)
            new_entries += 1

    save_signals_log(log, LOG_PATH)
    print(f"Signals log updated. New entries: {new_entries}")


if __name__ == "__main__":
    main()

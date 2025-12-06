# bots/generate_backtest_signals_from_csv.py

import os
import json
from typing import Dict, List, Tuple

import pandas as pd

# FICHIER DE SORTIE (log de signaux pour le backtest)
OUT_PATH = "data/signals_log_backtest.json"

# CONFIG : mapping (universe, strategy) -> chemin CSV
# Adapte simplement les chemins ci-dessous à tes fichiers réels.
CSV_CONFIG: Dict[Tuple[str, str], str] = {
    ("sp500", "phoenix"): "data/backtest_sp500_phoenix.csv",
    ("sp500", "pullback"): "data/backtest_sp500_pullback.csv",
    ("crypto", "phoenix"): "data/backtest_crypto_phoenix.csv",
    ("crypto", "pullback"): "data/backtest_crypto_pullback.csv",
}

# On attend au minimum ces colonnes dans chaque CSV :
# - date_signal
# - ticker
# - entry_price
# - stop_loss


def load_csv_safe(path: str) -> pd.DataFrame:
    """Charge un CSV ou renvoie un DataFrame vide si problème."""
    if not os.path.exists(path):
        print(f"[WARN] Fichier introuvable : {path}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(path)
    except Exception as e:
        print(f"[WARN] Erreur de lecture CSV {path}: {e}")
        return pd.DataFrame()

    return df


def normalize_columns(df: pd.DataFrame, path: str) -> pd.DataFrame:
    """
    S'assure que le DataFrame possède les colonnes attendues.
    Essaie d'être un peu tolérant sur les noms (date / date_signal, sl / stop_loss, etc.).
    """
    cols = {c.lower(): c for c in df.columns}

    # Date
    if "date_signal" in cols:
        date_col = cols["date_signal"]
    elif "date" in cols:
        date_col = cols["date"]
    else:
        raise ValueError(f"{path}: colonne 'date_signal' ou 'date' manquante")

    # Ticker
    if "ticker" in cols:
        ticker_col = cols["ticker"]
    elif "symbol" in cols:
        ticker_col = cols["symbol"]
    else:
        raise ValueError(f"{path}: colonne 'ticker' ou 'symbol' manquante")

    # Entry price
    if "entry_price" in cols:
        entry_col = cols["entry_price"]
    elif "close" in cols:
        entry_col = cols["close"]
    elif "price" in cols:
        entry_col = cols["price"]
    else:
        raise ValueError(f"{path}: colonne 'entry_price' / 'close' / 'price' manquante")

    # Stop loss
    if "stop_loss" in cols:
        sl_col = cols["stop_loss"]
    elif "sl" in cols:
        sl_col = cols["sl"]
    elif "stop" in cols:
        sl_col = cols["stop"]
    else:
        raise ValueError(f"{path}: colonne 'stop_loss' / 'sl' / 'stop' manquante")

    df_norm = pd.DataFrame(
        {
            "date_signal": df[date_col],
            "ticker": df[ticker_col],
            "entry_price": df[entry_col],
            "stop_loss": df[sl_col],
        }
    )

    return df_norm


def build_backtest_log() -> List[Dict]:
    """
    Construit la liste des entrées de log à partir des 4 CSV.
    Format de sortie compatible avec log_signals.py / perf_summary.py.
    """
    all_entries: List[Dict] = []

    for (universe, strategy), path in CSV_CONFIG.items():
        df = load_csv_safe(path)
        if df.empty:
            print(f"[INFO] {path}: DataFrame vide, on skip.")
            continue

        try:
            df = normalize_columns(df, path)
        except ValueError as e:
            print(f"[ERROR] {e}")
            continue

        # Normalisation des types
        df["date_signal"] = pd.to_datetime(df["date_signal"])
        df = df.dropna(subset=["date_signal", "ticker", "entry_price", "stop_loss"])

        # Boucle sur les lignes
        for _, row in df.iterrows():
            date_iso = row["date_signal"].date().isoformat()
            ticker = str(row["ticker"]).strip().upper()

            try:
                entry_price = float(row["entry_price"])
                stop_loss = float(row["stop_loss"])
            except Exception:
                # ligne pourrie → on skip
                continue

            if entry_price <= 0 or stop_loss <= 0:
                continue

            _id = f"{universe}_{strategy}_{ticker}_{date_iso}"

            entry = {
                "id": _id,
                "date_signal": date_iso,
                "ticker": ticker,
                "universe": universe,
                "strategy": strategy,
                "initial_data": {
                    "close_j": entry_price,
                    "stop_loss_technical": stop_loss,
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

            all_entries.append(entry)

        print(
            f"[INFO] {path}: ajout de {len(df)} signaux "
            f"pour {universe}_{strategy}"
        )

    # Tri pour avoir un fichier propre / stable
    all_entries_sorted = sorted(
        all_entries,
        key=lambda e: (
            e.get("date_signal", ""),
            e.get("universe", ""),
            e.get("strategy", ""),
            e.get("ticker", ""),
        ),
    )

    return all_entries_sorted


def main():
    log = build_backtest_log()

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(log, f, indent=2)

    print(f"[OK] Backtest log généré : {OUT_PATH} ({len(log)} signaux)")


if __name__ == "__main__":
    main()

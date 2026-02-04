# bots/indicators.py
# Fonctions d'indicateurs techniques partagées

import pandas as pd


def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    """Calcule la moyenne mobile simple (SMA)."""
    return series.rolling(window=window).mean()


def calculate_ema(series: pd.Series, window: int) -> pd.Series:
    """Calcule la moyenne mobile exponentielle (EMA)."""
    return series.ewm(span=window, adjust=False).mean()


def calculate_rsi(series: pd.Series, window: int = 14, method: str = "sma") -> pd.Series:
    """
    Calcule le RSI (Relative Strength Index).

    Args:
        series: Série de prix (Close)
        window: Période du RSI (default: 14)
        method: "sma" pour moyenne simple, "ema" pour moyenne exponentielle

    Returns:
        Série pandas avec les valeurs RSI
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    if method == "ema":
        avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    else:
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def normalize(value: float, min_val: float, max_val: float, clip: bool = True) -> float:
    """
    Normalise une valeur entre 0 et 1.

    Args:
        value: Valeur à normaliser
        min_val: Borne inférieure
        max_val: Borne supérieure
        clip: Si True, clipe le résultat entre 0 et 1

    Returns:
        Valeur normalisée entre 0 et 1
    """
    if max_val == min_val:
        return 0.0
    x = (value - min_val) / (max_val - min_val)
    if clip:
        x = max(0.0, min(1.0, x))
    return x

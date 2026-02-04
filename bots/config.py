# bots/config.py
# Configuration centralisée pour tous les bots

import os

# =========================
# CHEMINS DES FICHIERS
# =========================

# Racine du projet (parent du dossier bots)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Fichiers de log des signaux
LOG_PATH = os.path.join(DATA_DIR, "signals_log.json")
LOG_PATH_BACKTEST = os.path.join(DATA_DIR, "signals_log_backtest.json")

# Fichiers de sortie des performances
OUT_PATH = os.path.join(DATA_DIR, "performance_summary.json")
OUT_PATH_BACKTEST = os.path.join(DATA_DIR, "performance_backtest.json")

# Fichiers de signaux S&P 500
BREAKOUT_FILE_SP500 = os.path.join(DATA_DIR, "sp500_breakout_pro.json")
PULLBACK_FILE_SP500 = os.path.join(DATA_DIR, "sp500_pullback_pro.json")

# Fichiers de signaux Crypto
BREAKOUT_FILE_CRYPTO = os.path.join(DATA_DIR, "crypto_breakout_pro.json")
PULLBACK_FILE_CRYPTO = os.path.join(DATA_DIR, "crypto_pullback_pro.json")

# =========================
# PARAMÈTRES S&P 500
# =========================

SP500_MIN_CANDLES = 220
SP500_MIN_DOLLAR_VOL = 5_000_000
SP500_SLEEP_BETWEEN_CALLS = 0.05

# =========================
# PARAMÈTRES CRYPTO
# =========================

CRYPTO_MIN_CANDLES = 90
CRYPTO_MIN_DOLLAR_VOL = 1_000_000
CRYPTO_SLEEP_BETWEEN_CALLS = 0.2

# Stablecoins à exclure
CRYPTO_STABLECOINS = [
    "USDT", "USDC", "DAI", "FDUSD", "TUSA", "USDD", "PYUSD",
    "USDP", "EURI", "USDE", "BUSD", "USDS"
]

# Tokens explicitement exclus (or tokenisé, etc.)
CRYPTO_EXCLUDED_SYMBOLS = [
    "XAUT", "PAXG", "BDX", "GOLD", "XAUt", "XAU", "XAUTBULL", "XAUTBEAR"
]

# Mots-clés dans le nom à exclure
CRYPTO_EXCLUDED_NAME_KEYWORDS = [
    "GOLD", "PAX GOLD", "TETHER GOLD", "DIGITAL GOLD"
]

# Fallback : nombre max d'actifs si les conditions strictes donnent 0
CRYPTO_FALLBACK_MAX_BREAKOUT = 10
CRYPTO_FALLBACK_MAX_PULLBACK = 10

# =========================
# PARAMÈTRES DE TRADING / SIMULATION
# =========================

SLIPPAGE_ENTRY = 1.001  # +0.1% à l'entrée
SLIPPAGE_EXIT = 0.999   # -0.1% à la sortie
MAX_BARS_IN_TRADE = 10  # Time-stop après 10 bougies
BREAKEVEN_R_THRESHOLD = 1.0  # Passage au BE après +1R

# =========================
# NOMS DE STRATÉGIES ET UNIVERS
# =========================

STRATEGIES = ["phoenix", "pullback"]
UNIVERSES = ["sp500", "crypto"]

# Clés pour les groupes de performance
STRATEGY_KEYS = [
    "sp500_phoenix",
    "sp500_pullback",
    "crypto_phoenix",
    "crypto_pullback"
]

# =========================
# SOURCES POUR LOG_SIGNALS
# =========================

SIGNAL_SOURCES = [
    (BREAKOUT_FILE_SP500, "sp500", "phoenix"),
    (PULLBACK_FILE_SP500, "sp500", "pullback"),
    (BREAKOUT_FILE_CRYPTO, "crypto", "phoenix"),
    (PULLBACK_FILE_CRYPTO, "crypto", "pullback"),
]

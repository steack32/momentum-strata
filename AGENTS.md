# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**Momentum Strata** is a French-language algorithmic trading signals platform that scans S&P 500 stocks and cryptocurrencies daily to detect two types of setups:
- **Phoenix (Breakout)**: Momentum breakouts with high volume on established uptrends
- **Pullback**: Technical pullbacks to SMA/EMA support within strong trends

The platform consists of Python bots for signal generation and a static frontend to display results.

## Tech Stack

- **Backend/Bots**: Python 3.14+ with `yfinance`, `ccxt` (Binance), `pandas`, `numpy`
- **Frontend**: Static HTML with Tailwind CSS v4, vanilla JavaScript
- **Data sources**: Wikipedia (S&P 500 list), CoinGecko (crypto list), Yahoo Finance, Binance

## Commands

### Tailwind CSS
```powershell
# Build CSS (from project root)
npx tailwindcss -i assets/css/input.css -o assets/css/tailwind.css --watch
```

### Run Bots
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Generate S&P 500 signals → outputs to data/sp500_*.json
python bots/bot_sp500_pro.py

# Generate Crypto signals → outputs to data/crypto_*.json
python bots/bot_crypto_pro.py

# Log new signals to historical tracking
python bots/log_signals.py

# Calculate live performance metrics
python bots/perf_summary.py

# Generate backtest signals and performance
python bots/generate_backtest_signals.py
python bots/perf_summary_backtest.py
```

## Architecture

### Python Bots (`bots/`)
```
config.py           # Centralized configuration (paths, thresholds, strategy params)
indicators.py       # Shared technical indicators (SMA, EMA, RSI, normalize)
bot_sp500_pro.py    # S&P 500 scanner → sp500_breakout_pro.json, sp500_pullback_pro.json
bot_crypto_pro.py   # Crypto scanner → crypto_breakout_pro.json, crypto_pullback_pro.json
trade_simulator.py  # Trade execution simulation (entry, SL, breakeven, time-stop)
log_signals.py      # Appends new signals to signals_log.json
perf_summary.py     # Calculates live performance from signals_log.json
json_utils.py       # JSON read/write utilities
```

**Data flow**: Bots fetch OHLCV data → compute indicators → apply filtering criteria → score signals → output JSON to `data/`

### Frontend (`assets/`)
```
css/input.css       # Tailwind source with custom styles
js/main.js          # Component loader (navbar, footer), mobile menu
js/shared.js        # Shared utilities (sparklines, formatters, loadSignalsData)
js/sp500.js         # S&P 500 page logic
js/crypto.js        # Crypto page logic  
js/dashboard.js     # Dashboard performance charts
components/         # navbar.html, footer.html (dynamically injected)
```

**Pages**: `index.html` (S&P 500), `crypto.html`, `dashboard.html`

### Data (`data/`)
Signal files follow this JSON structure:
```json
{
  "date_mise_a_jour": "DD/MM/YYYY",
  "picks": {
    "TICKER": {
      "name": "...", "score": 85.5, "entry_price": 123.45,
      "stop_loss": 115.00, "rsi": 62.5, "trend_pct": 12.3,
      "vol_ratio": 2.5, "history": [...]
    }
  }
}
```

## Key Conventions

- **Scoring**: All strategies use a normalized 0-100 score combining trend strength, RSI, volume ratio, and price position
- **Stop Loss**: Calculated from volatility (ATR-based) or previous candle low
- **Trade Simulation Rules**:
  - Entry at next day's Open with +0.1% slippage
  - Breakeven activated when price reaches +1R
  - Time-stop exit at Close of 10th bar
  - Exit with -0.1% slippage
- **Liquidity filters**: S&P 500 requires $5M daily dollar volume, Crypto requires $1M
- **Crypto exclusions**: Stablecoins, wrapped tokens, and gold-backed tokens are filtered out

## Language

All user-facing content (HTML, comments in some files) is in **French**. Code identifiers and technical documentation are in English.

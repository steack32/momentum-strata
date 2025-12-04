import yfinance as yf
import pandas as pd
import json
import requests
import time

# --- FONCTIONS TECHNIQUES (REMPLACEMENT PANDAS_TA) ---
# Ces fonctions remplacent la librairie qui posait problème
def calculate_sma(series, window):
    return series.rolling(window=window).mean()

def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_sp500_tickers():
    """
    Récupère la liste S&P 500 via Wikipedia.
    """
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        table = pd.read_html(url)
        df = table[0]
        tickers = df['Symbol'].tolist()
        # Correction pour Yahoo Finance (BRK.B -> BRK-B)
        tickers = [t.replace('.', '-') for t in tickers]
        print(f"✅ Liste S&P 500 récupérée : {len(tickers)} actions.")
        return tickers
    except Exception as e:
        print(f"⚠️ Erreur récupération S&P 500. Utilisation liste de secours.")
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B", "LLY", "V"]

def analyze_market():
    tickers = get_sp500_tickers()
    
    pullback_picks = {}
    breakout_picks = {}
    
    print("🚀 Analyse S&P 500 Pro (Native) lancée...")
    
    for ticker in tickers:
        try:
            # Téléchargement
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            
            if len(df) < 200:
                continue
            
            # Nettoyage MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # --- CALCULS NATIFS (PLUS DE PANDAS_TA) ---
            df['SMA_200'] = calculate_sma(df['Close'], 200)
            df['SMA_50']  = calculate_sma(df['Close'], 50)
            df['RSI']     = calculate_rsi(df['Close'], 14)
            df['Vol_Avg'] = calculate_sma(df['Volume'], 20)

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            price = curr['Close']
            sma200 = curr['SMA_200']
            
            if pd.isna(sma200) or pd.isna(price): continue

            # --- STRATÉGIE 1 : PHOENIX (BREAKOUT) ---
            vol_ratio = curr['Volume'] / curr['Vol_Avg'] if curr['Vol_Avg'] > 0 else 0
            
            if (price > sma200) and (vol_ratio > 2.0) and (price > prev['Close']):
                score = ((price - sma200) / sma200) * 100
                stop_loss = min(prev['Low'], price * 0.95)

                breakout_picks[ticker] = {
                    "name": ticker,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "vol_ratio": round(vol_ratio, 1),
                    "history": df['Close'].tail(30).values.tolist()
                }

            # --- STRATÉGIE 2 : PULLBACK (REBOND) ---
            dist_sma50 = (price - curr['SMA_50']) / curr['SMA_50']
            
            if (price > sma200) and (curr['RSI'] < 60) and (abs(dist_sma50) < 0.03):
                score = ((price - sma200) / sma200) * 100
                stop_loss = curr['SMA_50'] * 0.97

                pullback_picks[ticker] = {
                    "name": ticker,
                    "score": score,
                    "entry_price": price,
                    "stop_loss": stop_loss,
                    "history": df['Close'].tail(30).values.tolist()
                }

        except Exception:
            continue

    print(f"✅ Analyse terminée. Breakout: {len(breakout_picks)} | Pullback: {len(pullback_picks)}")

    # Tri des résultats
    breakout_sorted = dict(sorted(breakout_picks.items(), key=lambda x: x[1]['vol_ratio'], reverse=True))
    pullback_sorted = dict(sorted(pullback_picks.items(), key=lambda x: x[1]['score'], reverse=True))

    return pullback_sorted, breakout_sorted

# --- MAIN ---
if __name__ == "__main__":
    pullback_data, breakout_data = analyze_market()
    
    today = pd.Timestamp.now().strftime("%d/%m/%Y")
    
    final_pullback = {"date_mise_a_jour": today, "picks": pullback_data}
    final_breakout = {"date_mise_a_jour": today, "picks": breakout_data}
    
    # Sauvegarde directe en version PRO
    with open("data/sp500_pullback_pro.json", "w") as f:
        json.dump(final_pullback, f, indent=4)
        
    with open("data/sp500_breakout_pro.json", "w") as f:
        json.dump(final_breakout, f, indent=4)
        
    print("💾 Fichiers S&P 500 sauvegardés.")
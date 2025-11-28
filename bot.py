import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# --- FONCTION POUR RÉCUPÉRER LE S&P 500 ---
def get_sp500_tickers():
    try:
        # Lecture du tableau Wikipedia
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = table[0]
        tickers = df['Symbol'].tolist()
        # Nettoyage (Yahoo utilise des tirets au lieu des points, ex: BRK.B -> BRK-B)
        tickers = [t.replace('.', '-') for t in tickers]
        return tickers
    except Exception as e:
        print(f"⚠️ Erreur récupération Wikipedia, utilisation liste de secours. ({e})")
        # Liste de secours si Wikipedia bloque
        return ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "TSLA", "META", "LLY", "JPM", "V"]

print(f"--- Momentum Strata V4 (S&P 500) ---")

# 1. RÉCUPÉRATION DE L'UNIVERS
tickers = get_sp500_tickers()
print(f"Universe chargé : {len(tickers)} actions du S&P 500.")

# 2. TÉLÉCHARGEMENT MASSIF (1 an d'historique)
print("Téléchargement des données (cela peut prendre 10-20 secondes)...")
try:
    # On télécharge tout d'un coup (plus rapide)
    data = yf.download(tickers, period="1y", interval="1wk", group_by='ticker', progress=True, auto_adjust=False, threads=True)
except Exception as e:
    print(f"❌ Erreur critique : {e}")
    exit()

# 3. ANALYSE ET FILTRAGE
valid_candidates = {}

print("\nAnalyse des tendances en cours...")

for ticker in tickers:
    try:
        # Récupération de la colonne 'Adj Close' pour ce ticker
        # Note: La structure du DataFrame change si on télécharge plusieurs tickers
        adj_close = data[ticker]['Adj Close'].dropna()

        if len(adj_close) < 50: # Pas assez d'historique
            continue

        current_price = adj_close.iloc[-1]
        
        # --- FILTRE 1 : PRIX MINIMUM (> 10$) ---
        if current_price < 10:
            continue

        # --- FILTRE 2 : TENDANCE DE FOND (SMA 200 jours / ~40 semaines) ---
        # Comme on est en données hebdo (1wk), 200 jours = env 40 semaines
        sma_40w = adj_close.rolling(window=40).mean().iloc[-1]
        
        # Si le prix est sous la moyenne mobile, on zappe
        if current_price < sma_40w:
            continue

        # --- CALCUL DU MOMENTUM (26 semaines / 6 mois) ---
        # Formule ROC (Rate of Change)
        momentum = (current_price / adj_close.iloc[-27]) - 1

        valid_candidates[ticker] = momentum

    except Exception:
        continue # On ignore silencieusement les erreurs de calculs sur un ticker

# 4. CLASSEMENT
if not valid_candidates:
    print("⚠️ Aucun candidat trouvé après filtrage.")
    exit()

# Conversion en Série pour trier
ranking = pd.Series(valid_candidates).sort_values(ascending=False)
top_5 = ranking.head(5)

print(f"\n✅ Top 5 trouvé parmi {len(valid_candidates)} candidats valides (filtre SMA200 appliqué).")

# 5. RÉCUPÉRATION DÉTAILLÉE (Pour les graphs du site)
export_data = {}

for ticker, score in top_5.items():
    print(f"   Traitement final : {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        infos = stock.info
        full_name = infos.get('shortName', infos.get('longName', ticker))
        
        # On reprend l'historique qu'on a déjà téléchargé pour gagner du temps
        # On prend les 30 dernières semaines
        history_series = data[ticker]['Adj Close'].dropna().tail(30).tolist()
        history_clean = [round(x, 2) for x in history_series]

        export_data[ticker] = {
            "score": score,
            "name": full_name,
            "history": history_clean
        }
    except:
        export_data[ticker] = {"score": score, "name": ticker, "history": []}

# 6. EXPORT
final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

with open("data.json", "w") as f:
    json.dump(final_payload, f)

print("\n🚀 Terminé. Données S&P 500 mises à jour.")
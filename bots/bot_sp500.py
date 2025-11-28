import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# --- 1. RÉCUPÉRATION DE LA LISTE S&P 500 ---
def get_sp500_tickers():
    try:
        # Lecture du tableau des entreprises sur Wikipédia
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = table[0]
        # Récupération des symboles (tickers)
        tickers = df['Symbol'].tolist()
        # Remplacement des points par des tirets pour la compatibilité yfinance (ex: BRK.B -> BRK-B)
        return [t.replace('.', '-') for t in tickers]
    except Exception as e:
        print(f"❌ Erreur lors de la récupération de la liste S&P 500 : {e}")
        # Liste de secours en cas d'erreur
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "META", "LLY", "JPM", "V", "XOM"]

print(f"--- Momentum Strata : S&P 500 Bot ---")
tickers = get_sp500_tickers()
print(f"Analyse de {len(tickers)} entreprises du S&P 500...")

# --- 2. TÉLÉCHARGEMENT MASSIF DES DONNÉES ---
# On télécharge 1 an d'historique journalier pour le calcul du momentum et les graphiques
try:
    print("Téléchargement des données historiques en cours...")
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=True, auto_adjust=False, threads=True)
except Exception as e:
    print(f"❌ Erreur critique lors du téléchargement : {e}")
    exit()

# --- 3. ANALYSE, FILTRAGE ET SÉLECTION ---
valid_candidates = {}
print("\nAnalyse des tendances et calcul du momentum...")

for ticker in tickers:
    try:
        # Récupération des prix de clôture ajustés
        adj_close = data[ticker]['Adj Close'].dropna()

        # Il faut au moins 6 mois de données (~126 jours de bourse) pour le momentum
        if len(adj_close) < 126: continue

        current_price = adj_close.iloc[-1]
        
        # --- FILTRE 1 : PRIX MINIMUM ---
        # On ignore les "penny stocks" pour éviter la volatilité excessive
        if current_price < 10:
            continue

        # --- CALCUL DU MOMENTUM (6 mois ~ 126 jours) ---
        # Formule ROC (Rate of Change) : (Prix actuel / Prix il y a 6 mois) - 1
        momentum = (current_price / adj_close.iloc[-126]) - 1

        valid_candidates[ticker] = momentum

    except Exception:
        # On ignore silencieusement les erreurs sur un ticker individuel
        continue

# --- 4. CLASSEMENT DU TOP 5 ---
if not valid_candidates:
    print("⚠️ Aucun candidat trouvé après filtrage.")
    exit()

# Tri décroissant des scores et sélection des 5 meilleurs
ranking = pd.Series(valid_candidates).sort_values(ascending=False)
top_5 = ranking.head(5)

print(f"\n✅ Top 5 S&P 500 identifié. Préparation des données détaillées...")

# --- 5. RÉCUPÉRATION DES DÉTAILS ET EXPORT JSON ---
export_data = {}

# On crée un objet Tickers pour récupérer les infos (noms) en une seule fois si possible
try:
    tickers_info = yf.Tickers(' '.join(top_5.index))
except:
    tickers_info = None

for ticker, score in top_5.items():
    print(f"   Traitement final : {ticker}...")
    try:
        # Récupération du nom complet de l'entreprise
        full_name = ticker # Valeur par défaut
        if tickers_info:
            try:
                infos = tickers_info.tickers[ticker].info
                # On essaie 'shortName' puis 'longName'
                full_name = infos.get('shortName', infos.get('longName', ticker))
            except:
                pass # On garde le ticker si le nom est introuvable

        # Récupération de l'historique pour le graphique Sparkline (30 derniers jours)
        # On utilise .tail(30) pour prendre les 30 dernières valeurs
        history_series = data[ticker]['Adj Close'].dropna().tail(30).tolist()
        # On arrondit les prix à 2 décimales pour le JSON
        history_clean = [round(x, 2) for x in history_series]

        # Construction de l'objet de données complet pour ce ticker
        export_data[ticker] = {
            "score": score,
            "name": full_name,
            "history": history_clean,
            # Placeholder pour les futures fonctionnalités (Stop Loss, etc.)
            "entry_min": None,
            "entry_max": None,
            "stop_loss": None
        }
    except Exception as e:
        print(f"   ⚠️ Erreur lors du traitement de {ticker}: {e}")
        # En cas d'erreur, on sauvegarde une version minimale pour ne pas bloquer le site
        export_data[ticker] = {"score": score, "name": ticker, "history": []}

# --- 6. SAUVEGARDE DU FICHIER JSON FINAL ---
# Structure finale attendue par le site web
final_payload = {
    "date_mise_a_jour": datetime.now().strftime("%d/%m/%Y"),
    "picks": export_data
}

# Sauvegarde dans le dossier data/
try:
    # On remonte d'un dossier (../) puis on va dans data/
    with open("../data/sp500.json", "w") as f:
        json.dump(final_payload, f)
    print("\n🚀 Terminé. Fichier 'data/sp500.json' mis à jour avec succès.")
except Exception as e:
    print(f"\n❌ Erreur lors de la sauvegarde du JSON : {e}")
    print("Vérifiez que vous lancez bien le script DEPUIS le dossier 'bots/' !")
// assets/js/dashboard.js
// Vue d'ensemble des signaux S&P 500 et Crypto

async function loadSignalsSummary(config) {
  const {
    url,
    countSelector,
    bestScoreSelector,
    dateSelector
  } = config;

  const countEl = document.querySelector(countSelector);
  const bestScoreEl = document.querySelector(bestScoreSelector);
  const dateEl = document.querySelector(dateSelector);

  if (!countEl || !bestScoreEl || !dateEl) return;

  // Valeurs par défaut
  countEl.textContent = "–";
  bestScoreEl.textContent = "–";
  dateEl.textContent = "–";

  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.error(`Erreur HTTP ${response.status} pour ${url}`);
      return;
    }

    const data = await response.json();
    const picks = data.picks || {};
    const entries = Object.values(picks);

    const count = entries.length;

    let bestScore = null;
    for (const item of entries) {
      const s = typeof item.score === "number" ? item.score : null;
      if (s !== null) {
        if (bestScore === null || s > bestScore) {
          bestScore = s;
        }
      }
    }

    // Mise à jour de l'UI
    countEl.textContent = count.toString();
    bestScoreEl.textContent = bestScore !== null ? bestScore.toFixed(1) : "–";
    dateEl.textContent = data.date_mise_a_jour || "–";
  } catch (error) {
    console.error("Erreur lors du chargement des données dashboard :", error);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // S&P 500 Phoenix
  loadSignalsSummary({
    url: "data/sp500_breakout_pro.json",
    countSelector: "#sp500-phoenix-count",
    bestScoreSelector: "#sp500-phoenix-best-score",
    dateSelector: "#sp500-phoenix-date"
  });

  // S&P 500 Pullback
  loadSignalsSummary({
    url: "data/sp500_pullback_pro.json",
    countSelector: "#sp500-pullback-count",
    bestScoreSelector: "#sp500-pullback-best-score",
    dateSelector: "#sp500-pullback-date"
  });

  // Crypto Phoenix
  loadSignalsSummary({
    url: "data/crypto_breakout_pro.json",
    countSelector: "#crypto-phoenix-count",
    bestScoreSelector: "#crypto-phoenix-best-score",
    dateSelector: "#crypto-phoenix-date"
  });

  // Crypto Pullback
  loadSignalsSummary({
    url: "data/crypto_pullback_pro.json",
    countSelector: "#crypto-pullback-count",
    bestScoreSelector: "#crypto-pullback-best-score",
    dateSelector: "#crypto-pullback-date"
  });
});

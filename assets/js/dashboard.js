// assets/js/dashboard.js

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function formatNumber(value, digits = 2) {
    if (value === null || value === undefined || isNaN(value)) return "–";
    return Number(value).toFixed(digits);
}

function updatePerfCard(key, baseId, stats) {
    const card = document.getElementById(baseId + "-card");
    const noteId = baseId + "-note";

    if (!card) return;

    if (!stats || !stats.nb_trades || stats.nb_trades === 0) {
        setText(baseId + "-nb", "0");
        setText(baseId + "-avgR", "–");
        setText(baseId + "-win", "–");
        setText(baseId + "-be", "–");
        setText(baseId + "-exp", "–");

        const note = document.getElementById(noteId);
        if (note) {
            note.textContent = "Pas encore assez d’historique pour afficher des statistiques robustes.";
        }
        return;
    }

    setText(baseId + "-nb", stats.nb_trades);
    setText(baseId + "-avgR", formatNumber(stats.avg_R, 3));
    setText(baseId + "-win", formatNumber(stats.winrate, 1));
    setText(baseId + "-be", formatNumber(stats.breakeven_rate, 1));
    setText(baseId + "-exp", formatNumber(stats.expectancy_R, 3));

    const note = document.getElementById(noteId);
    if (note) {
        note.textContent =
            "Données issues de trades clôturés uniquement, en mode backtest trader (stop, breakeven, time-stop, slippage).";
    }
}

async function loadPerformanceSummary() {
    const loadingEl = document.getElementById("perf-loading");
    const errorEl = document.getElementById("perf-error");

    try {
        const response = await fetch("data/performance_summary.json", { cache: "no-cache" });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (loadingEl) loadingEl.classList.add("hidden");
        if (errorEl) errorEl.classList.add("hidden");

        // Date de mise à jour
        if (data.last_update) {
            setText("perf-last-update", data.last_update);
        }

        updatePerfCard("sp500_phoenix", "sp500-phoenix", data.sp500_phoenix);
        updatePerfCard("sp500_pullback", "sp500-pullback", data.sp500_pullback);
        updatePerfCard("crypto_phoenix", "crypto-phoenix", data.crypto_phoenix);
        updatePerfCard("crypto_pullback", "crypto-pullback", data.crypto_pullback);
    } catch (error) {
        console.error("Erreur lors du chargement de performance_summary.json :", error);
        if (loadingEl) loadingEl.classList.add("hidden");
        if (errorEl) errorEl.classList.remove("hidden");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadPerformanceSummary();
});

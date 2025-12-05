// assets/js/dashboard.js

let equityChartInstance = null;

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function formatNumber(value, digits = 2) {
    if (value === null || value === undefined || isNaN(value)) return "–";
    return Number(value).toFixed(digits);
}

function updatePerfCard(baseId, stats) {
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

function renderEquityChart(equityCurveAll) {
    const container = document.getElementById("equity-chart-container");
    const canvas = document.getElementById("equity-chart");
    const noDataEl = document.getElementById("equity-no-data");

    if (!container || !canvas) return;

    if (!equityCurveAll || typeof equityCurveAll !== "object") {
        container.classList.add("hidden");
        if (noDataEl) noDataEl.classList.remove("hidden");
        return;
    }

    // On utilise les courbes par stratégie (on peut garder la globale pour plus tard)
    const curves = {
        "sp500_phoenix": equityCurveAll.sp500_phoenix,
        "sp500_pullback": equityCurveAll.sp500_pullback,
        "crypto_phoenix": equityCurveAll.crypto_phoenix,
        "crypto_pullback": equityCurveAll.crypto_pullback,
    };

    // Récupération de toutes les dates utilisées
    const dateSet = new Set();
    Object.values(curves).forEach((curve) => {
        if (curve && Array.isArray(curve.dates)) {
            curve.dates.forEach((d) => dateSet.add(d));
        }
    });

    const allDates = Array.from(dateSet).sort(); // format YYYY-MM-DD → tri lexicographique = tri chronologique

    // S'il n'y a aucune date / aucun trade, on masque le graphique
    if (allDates.length === 0) {
        container.classList.add("hidden");
        if (noDataEl) noDataEl.classList.remove("hidden");
        return;
    }

    // Construction des datasets alignés sur allDates
    const datasetsMeta = [
        {
            key: "sp500_phoenix",
            label: "S&P 500 • Phoenix",
            borderColor: "rgba(251, 191, 36, 1)",      // amber-400
            backgroundColor: "rgba(251, 191, 36, 0.12)",
        },
        {
            key: "sp500_pullback",
            label: "S&P 500 • Pullback",
            borderColor: "rgba(34, 197, 94, 1)",       // emerald-500
            backgroundColor: "rgba(34, 197, 94, 0.12)",
        },
        {
            key: "crypto_phoenix",
            label: "Crypto • Phoenix",
            borderColor: "rgba(56, 189, 248, 1)",      // sky-400
            backgroundColor: "rgba(56, 189, 248, 0.12)",
        },
        {
            key: "crypto_pullback",
            label: "Crypto • Pullback",
            borderColor: "rgba(244, 114, 182, 1)",     // pink-400
            backgroundColor: "rgba(244, 114, 182, 0.12)",
        },
    ];

    const datasets = [];

    datasetsMeta.forEach((meta) => {
        const curve = curves[meta.key];
        if (!curve || !Array.isArray(curve.dates) || curve.dates.length === 0) {
            return; // pas encore de trades pour cette stratégie
        }

        const dateToValue = {};
        curve.dates.forEach((d, idx) => {
            dateToValue[d] = curve.equity_pct[idx];
        });

        const serie = allDates.map((d) =>
            Object.prototype.hasOwnProperty.call(dateToValue, d) ? dateToValue[d] : null
        );

        datasets.push({
            label: meta.label,
            data: serie,
            borderColor: meta.borderColor,
            backgroundColor: meta.backgroundColor,
            borderWidth: 2,
            tension: 0.25,
            pointRadius: 0,
            fill: false,
        });
    });

    if (datasets.length === 0) {
        container.classList.add("hidden");
        if (noDataEl) noDataEl.classList.remove("hidden");
        return;
    }

    container.classList.remove("hidden");
    if (noDataEl) noDataEl.classList.add("hidden");

    const ctx = canvas.getContext("2d");

    if (equityChartInstance) {
        equityChartInstance.destroy();
    }

    equityChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: allDates,
            datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false,
            },
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        color: "#cbd5f5",
                        font: { size: 11 },
                        usePointStyle: true,
                    },
                },
                tooltip: {
                    callbacks: {
                        title: function (items) {
                            if (!items || !items.length) return "";
                            return "Date : " + items[0].label;
                        },
                        label: function (context) {
                            const v = context.parsed.y;
                            if (v === null || v === undefined) return context.dataset.label + " : n.d.";
                            return context.dataset.label + " : " + v.toFixed(2) + " %";
                        },
                    },
                },
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: "Temps",
                        color: "#94a3b8",
                        font: { size: 11 },
                    },
                    ticks: {
                        maxTicksLimit: 8,
                        color: "#64748b",
                        font: { size: 10 },
                    },
                    grid: {
                        color: "rgba(148, 163, 184, 0.15)",
                    },
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: "Gains cumulés (%)",
                        color: "#94a3b8",
                        font: { size: 11 },
                    },
                    ticks: {
                        color: "#64748b",
                        font: { size: 10 },
                    },
                    grid: {
                        color: "rgba(148, 163, 184, 0.15)",
                    },
                },
            },
        },
    });
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

        // Cartes stratégiques
        updatePerfCard("sp500-phoenix", data.sp500_phoenix);
        updatePerfCard("sp500-pullback", data.sp500_pullback);
        updatePerfCard("crypto-phoenix", data.crypto_phoenix);
        updatePerfCard("crypto-pullback", data.crypto_pullback);

        // Courbes de performance cumulée (par stratégie)
        renderEquityChart(data.equity_curve);
    } catch (error) {
        console.error("Erreur lors du chargement de performance_summary.json :", error);
        if (loadingEl) loadingEl.classList.add("hidden");
        if (errorEl) errorEl.classList.remove("hidden");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadPerformanceSummary();
});

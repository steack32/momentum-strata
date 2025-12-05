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

function renderEquityChart(equityCurve) {
    const container = document.getElementById("equity-chart-container");
    const canvas = document.getElementById("equity-chart");
    const noDataEl = document.getElementById("equity-no-data");

    if (!container || !canvas) return;

    const hasData =
        equityCurve &&
        Array.isArray(equityCurve.dates) &&
        equityCurve.dates.length > 0 &&
        Array.isArray(equityCurve.equity_pct) &&
        equityCurve.equity_pct.length === equityCurve.dates.length;

    if (!hasData) {
        container.classList.add("hidden");
        if (noDataEl) noDataEl.classList.remove("hidden");
        return;
    }

    container.classList.remove("hidden");
    if (noDataEl) noDataEl.classList.add("hidden");

    const ctx = canvas.getContext("2d");
    const labels = equityCurve.dates;
    const values = equityCurve.equity_pct;

    if (equityChartInstance) {
        equityChartInstance.destroy();
    }

    equityChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Gains cumulés (%)",
                    data: values,
                    borderColor: "rgba(56, 189, 248, 1)",    // sky-400
                    backgroundColor: "rgba(56, 189, 248, 0.15)",
                    borderWidth: 2,
                    tension: 0.25,
                    pointRadius: 0,
                    fill: true,
                },
            ],
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
                    display: false,
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const v = context.parsed.y;
                            return "Gains cumulés : " + v.toFixed(2) + " %";
                        },
                    },
                },
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: "Date",
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

        // Courbe de performance cumulée globale
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

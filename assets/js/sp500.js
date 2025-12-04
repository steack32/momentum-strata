// assets/js/sp500.js
// Logique spécifique à la page S&P 500 (index.html)

/**
 * Génère un mini-graphe (sparkline) en SVG à partir d'un tableau de prix.
 */
function createSparkline(data, width = 120, height = 40, color = "#10b981") {
    if (!Array.isArray(data) || data.length < 2) return "";

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const paddingY = 5;
    const effectiveHeight = height - paddingY * 2;
    const stepX = width / (data.length - 1);

    const path = data
        .map((value, index) => {
            const x = index * stepX;
            const y = (height - paddingY) - ((value - min) / range * effectiveHeight);
            const cmd = index === 0 ? "M" : "L";
            return `${cmd} ${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");

    const lastX = width;
    const lastY = (height - paddingY) - ((data[data.length - 1] - min) / range * effectiveHeight);

    return `
        <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" class="overflow-visible">
            <path d="${path}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"></path>
            <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="2" fill="${color}"></circle>
        </svg>
    `;
}

function formatNumber(value, digits = 0) {
    if (value === null || value === undefined || isNaN(value)) return "-";
    return Number(value).toLocaleString("en-US", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
    });
}

/**
 * Gestion des stats du HERO (nombre de signaux Phoenix / Pullback).
 */
const heroStats = {
    phoenix: null,
    pullback: null
};

function updateHeroStats() {
    const phoenixEl = document.getElementById("hero-phoenix-count");
    const pullbackEl = document.getElementById("hero-pullback-count");

    if (phoenixEl && heroStats.phoenix !== null) {
        phoenixEl.textContent = heroStats.phoenix.toString();
    }
    if (pullbackEl && heroStats.pullback !== null) {
        pullbackEl.textContent = heroStats.pullback.toString();
    }
}

/**
 * Injecte une ligne dans un tbody HTML pour un signal donné.
 */
function appendSignalRow(tbody, ticker, info, options) {
    const { variant } = options || {}; // "phoenix" ou "pullback"

    const price = info.entry_price || 0;
    const stop = info.stop_loss || 0;
    const score = info.score || 0;
    const rsi = info.rsi;
    const volRatio = info.vol_ratio;
    const trendPct = info.trend_pct;
    const dollarVol = info.dollar_vol_avg20;
    const history = info.history || [];

    // --- SCORE COLOR (gradient) ---
    const scoreBadge =
        score >= 80 ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" :
        score >= 60 ? "bg-amber-500/20 text-amber-300 border-amber-500/40" :
        "bg-slate-700/30 text-slate-300 border-slate-600/40";

    // --- RSI COLOR ---
    const rsiColor =
        typeof rsi === "number" && rsi > 70 ? "text-rose-400" :
        typeof rsi === "number" && rsi < 30 ? "text-blue-300" :
        "text-slate-300";

    // --- VOLUME ---
    const volText =
        typeof volRatio === "number"
            ? `x${volRatio.toFixed(1)} • $${formatNumber(dollarVol, 0)}`
            : `$${formatNumber(dollarVol, 0)}`;

    // --- TREND ---
    const trendShort =
        typeof trendPct === "number"
            ? (trendPct >= 0
                ? `+${trendPct.toFixed(1)}% / SMA200`
                : `${trendPct.toFixed(1)}% / SMA200`)
            : "Trend n.d.";

    // --- SPARKLINE ---
    const sparkColor = variant === "phoenix" ? "#fbbf24" : "#10b981";
    const sparkline = history && history.length > 1
        ? createSparkline(history, 120, 40, sparkColor)
        : "";

    const tradingViewUrl =
        `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ticker)}`;

    const rowHtml = `
        <tr class="hover:bg-slate-800/40 border-b border-slate-800/40 transition-all">
            
            <!-- Nom -->
            <td class="px-6 py-4 align-top">
                <div class="font-semibold text-slate-100 leading-tight">${info.name || ticker}</div>
                <div class="text-[11px] text-slate-500 mt-0.5">${ticker}</div>
            </td>

            <!-- Tendance & Volume -->
            <td class="px-6 py-4 hidden md:table-cell align-top">
                <div class="flex flex-col gap-1">
                    <span class="text-[11px] text-amber-300 font-medium">${trendShort}</span>
                    <span class="text-[10px] text-slate-400">Vol : ${volText}</span>
                </div>
            </td>

            <!-- Score & RSI -->
            <td class="px-6 py-4 align-top">
                <div class="flex flex-col gap-1">
                    <span class="text-xs font-semibold px-2 py-0.5 rounded border ${scoreBadge}">
                        Score : ${score.toFixed(1)}
                    </span>
                    <span class="text-[10px] ${rsiColor}">
                        RSI : ${typeof rsi === "number" ? rsi.toFixed(1) : "-"}
                    </span>
                </div>
            </td>

            <!-- Prix -->
            <td class="px-6 py-4 hidden sm:table-cell align-top font-mono text-xs text-slate-300">
                $${formatNumber(price, 2)}
            </td>

            <!-- Stop -->
            <td class="px-6 py-4 hidden sm:table-cell align-top font-mono text-xs text-rose-400">
                $${formatNumber(stop, 2)}
            </td>

            <!-- Chart -->
            <td class="px-6 py-4 align-top text-right">
                <div class="flex flex-col items-end gap-2">
                    ${sparkline ? `<div class="w-[120px] h-[40px] opacity-90">${sparkline}</div>` : ""}
                    <a href="${tradingViewUrl}" target="_blank" rel="noopener"
                        class="text-[11px] font-medium text-blue-300 hover:text-blue-200">
                        Voir → 
                    </a>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", rowHtml);
}


async function loadSp500Phoenix() {
    const dateEl = document.getElementById("date-phoenix");
    const tbody = document.getElementById("table-phoenix");
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Chargement des données...</td></tr>';

    try {
        const response = await fetch("data/sp500_breakout_pro.json");
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        const data = await response.json();

        if (dateEl) {
            dateEl.textContent = data.date_mise_a_jour || "-";
        }

        const entries = Object.entries(data.picks || {});
        tbody.innerHTML = "";

        // Mise à jour des stats Hero pour Phoenix
        heroStats.phoenix = entries.length;
        updateHeroStats();

        if (!entries.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Aucun breakout détecté aujourd\'hui.</td></tr>';
            return;
        }

        entries.forEach(([ticker, info]) => {
            appendSignalRow(tbody, ticker, info, { variant: "phoenix" });
        });
    } catch (error) {
        console.error("Erreur chargement S&P 500 Phoenix :", error);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-rose-400">Erreur lors du chargement des données.</td></tr>';
        if (dateEl) {
            dateEl.textContent = "-";
        }
        // En cas d'erreur, on laisse les stats Hero sur leur valeur par défaut (–)
    }
}

async function loadSp500Pullback() {
    const dateEl = document.getElementById("date-pullback");
    const tbody = document.getElementById("table-pullback");
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Chargement des données...</td></tr>';

    try {
        const response = await fetch("data/sp500_pullback_pro.json");
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        const data = await response.json();

        if (dateEl) {
            dateEl.textContent = data.date_mise_a_jour || "-";
        }

        const entries = Object.entries(data.picks || {});
        tbody.innerHTML = "";

        // Mise à jour des stats Hero pour Pullback
        heroStats.pullback = entries.length;
        updateHeroStats();

        if (!entries.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Aucun pullback haussier détecté aujourd\'hui.</td></tr>';
            return;
        }

        entries.forEach(([ticker, info]) => {
            appendSignalRow(tbody, ticker, info, { variant: "pullback" });
        });
    } catch (error) {
        console.error("Erreur chargement S&P 500 Pullback :", error);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-rose-400">Erreur lors du chargement des données.</td></tr>';
        if (dateEl) {
            dateEl.textContent = "-";
        }
        // En cas d'erreur, on laisse les stats Hero sur leur valeur par défaut (–)
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadSp500Phoenix();
    loadSp500Pullback();
});

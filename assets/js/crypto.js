// assets/js/crypto.js
// Logique spécifique à la page Crypto (crypto.html)

/**
 * Génère un mini-graphe (sparkline) en SVG à partir d'un tableau de prix.
 */
function createSparkline(data, width = 120, height = 40, color = "#a855f7") {
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
 * Ajoute une ligne de signal crypto dans un tbody.
 */
function appendCryptoRow(tbody, symbol, info, options) {
    const { variant } = options || {}; // "phoenix" (breakout) ou "pullback"

    const price = info.entry_price || 0;
    const stop = info.stop_loss || 0;
    const score = info.score || 0;
    const rsi = info.rsi;
    const trendPct = info.trend_pct;
    const dollarVol = info.dollar_vol_avg20;
    const history = info.history || [];

    const scoreColor =
        score >= 80 ? "text-emerald-400" :
        score >= 60 ? "text-amber-300" :
        "text-slate-300";

    const rsiColor =
        typeof rsi === "number" && rsi > 70
            ? "text-rose-400"
            : "text-slate-300";

    const volText = `$${formatNumber(dollarVol, 0)} / jour`;

    const trendText =
        typeof trendPct === "number"
            ? (trendPct >= 0
                ? `Trend : +${trendPct.toFixed(1)}% au-dessus de la SMA200`
                : `Trend : ${trendPct.toFixed(1)}% sous la SMA200`)
            : "Trend : n.d.";

    const sparklineColor = variant === "phoenix" ? "#a855f7" : "#10b981";
    const sparkline = history && history.length > 1
        ? createSparkline(history, 120, 40, sparklineColor)
        : "";

    const tradingViewUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`;

    const rowHtml = `
        <tr class="hover:bg-slate-800/50 border-b border-slate-800/50 transition-colors">
            <td class="px-6 py-4 align-top">
                <div class="font-bold text-slate-100 leading-snug">${info.name || symbol}</div>
                <div class="text-[11px] text-slate-500 mt-0.5">${symbol}</div>
            </td>
            <td class="px-6 py-4 hidden md:table-cell align-top">
                <div class="flex flex-col gap-1">
                    <span class="text-xs font-medium text-purple-300">${trendText}</span>
                    <span class="text-[10px] text-slate-400">Vol moyen 20j : ${volText}</span>
                </div>
            </td>
            <td class="px-6 py-4 align-top">
                <div class="flex flex-col items-start gap-1">
                    <span class="text-xs ${scoreColor} font-semibold">Score : ${score.toFixed(1)}</span>
                    <span class="text-[10px] ${rsiColor}">RSI : ${typeof rsi === "number" ? rsi.toFixed(1) : "-"}</span>
                </div>
            </td>
            <td class="px-6 py-4 hidden sm:table-cell align-top text-slate-300 font-mono text-xs">
                $${formatNumber(price, 4)}
            </td>
            <td class="px-6 py-4 hidden sm:table-cell align-top text-rose-400 font-mono text-xs">
                $${formatNumber(stop, 4)}
            </td>
            <td class="px-6 py-4 text-right align-top">
                <div class="flex flex-col items-end gap-2">
                    ${sparkline ? `<div class="w-[120px] h-[40px] inline-block">${sparkline}</div>` : ""}
                    <a href="${tradingViewUrl}" target="_blank" rel="noopener"
                       class="inline-flex items-center text-[11px] font-medium text-purple-300 hover:text-purple-200">
                        Voir &rarr;
                    </a>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", rowHtml);
}

async function loadCryptoPhoenix() {
    const dateEl = document.getElementById("date-phoenix");
    const tbody = document.getElementById("table-phoenix");
    const heroCountEl = document.getElementById("hero-crypto-phoenix-count");

    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Chargement des données...</td></tr>';
    if (heroCountEl) heroCountEl.textContent = "–";

    try {
        const response = await fetch("data/crypto_breakout_pro.json");
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        const data = await response.json();
        if (dateEl) {
            dateEl.textContent = data.date_mise_a_jour || "-";
        }
        const entries = Object.entries(data.picks || {});
        tbody.innerHTML = "";

        if (!entries.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Aucune opportunité haute qualité détectée aujourd\'hui.</td></tr>';
            if (heroCountEl) heroCountEl.textContent = "0";
            return;
        }

        entries.forEach(([symbol, info]) => {
            appendCryptoRow(tbody, symbol, info, { variant: "phoenix" });
        });

        if (heroCountEl) {
            heroCountEl.textContent = String(entries.length);
        }
    } catch (error) {
        console.error("Erreur chargement Crypto Phoenix :", error);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-rose-400">Erreur lors du chargement des données.</td></tr>';
        if (dateEl) {
            dateEl.textContent = "-";
        }
        if (heroCountEl) {
            heroCountEl.textContent = "–";
        }
    }
}

async function loadCryptoPullback() {
    const dateEl = document.getElementById("date-pullback");
    const tbody = document.getElementById("table-pullback");
    const heroCountEl = document.getElementById("hero-crypto-pullback-count");

    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Chargement des données...</td></tr>';
    if (heroCountEl) heroCountEl.textContent = "–";

    try {
        const response = await fetch("data/crypto_pullback_pro.json");
        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }
        const data = await response.json();
        if (dateEl) {
            dateEl.textContent = data.date_mise_a_jour || "-";
        }
        const entries = Object.entries(data.picks || {});
        tbody.innerHTML = "";

        if (!entries.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Aucune consolidation haussière détectée aujourd\'hui.</td></tr>';
            if (heroCountEl) heroCountEl.textContent = "0";
            return;
        }

        entries.forEach(([symbol, info]) => {
            appendCryptoRow(tbody, symbol, info, { variant: "pullback" });
        });

        if (heroCountEl) {
            heroCountEl.textContent = String(entries.length);
        }
    } catch (error) {
        console.error("Erreur chargement Crypto Pullback :", error);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-rose-400">Erreur lors du chargement des données.</td></tr>';
        if (dateEl) {
            dateEl.textContent = "-";
        }
        if (heroCountEl) {
            heroCountEl.textContent = "–";
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadCryptoPhoenix();
    loadCryptoPullback();
});

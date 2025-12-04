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
 * Injecte une ligne dans un tbody HTML pour un signal donné
 * + une carte mobile si un conteneur mobile est fourni.
 */
function appendSignalRow(tbody, ticker, info, options) {
    const { variant, cardContainer } = options || {}; // "phoenix" ou "pullback"

    const price = info.entry_price || 0;
    const stop = info.stop_loss || 0;
    const score = info.score || 0;
    const rsi = info.rsi;
    const volRatio = info.vol_ratio;
    const trendPct = info.trend_pct;
    const dollarVol = info.dollar_vol_avg20;
    const history = info.history || [];
    const name = info.name || ticker;

    const scoreColor =
        score >= 80 ? "text-emerald-400" :
        score >= 60 ? "text-amber-300" :
        "text-slate-300";

    const rsiColor =
        typeof rsi === "number" && rsi > 70
            ? "text-rose-400"
            : "text-slate-300";

    const volText =
        typeof volRatio === "number"
            ? `Vol x${volRatio.toFixed(1)} • $${formatNumber(dollarVol, 0)}`
            : `$${formatNumber(dollarVol, 0)} / jour`;

    const trendText =
        typeof trendPct === "number"
            ? (trendPct >= 0
                ? `Trend : +${trendPct.toFixed(1)}% au-dessus de la SMA200`
                : `Trend : ${trendPct.toFixed(1)}% sous la SMA200`)
            : "Trend : n.d.";

    const sparklineColor = variant === "phoenix" ? "#fbbf24" : "#10b981";
    const sparkline = history && history.length > 1
        ? createSparkline(history, 120, 40, sparklineColor)
        : "";

    const tradingViewUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ticker)}`;

    // Ligne de tableau (desktop)
    const rowHtml = `
        <tr class="hover:bg-slate-800/50 border-b border-slate-800/50 transition-colors">
            <td class="px-6 py-4 align-top">
                <div class="font-bold text-slate-100 leading-snug">${name}</div>
                <div class="text-[11px] text-slate-500 mt-0.5">${ticker}</div>
            </td>
            <td class="px-6 py-4 hidden md:table-cell align-top">
                <div class="flex flex-col gap-1">
                    <span class="text-xs font-medium text-amber-300">${trendText}</span>
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
                $${formatNumber(price, 2)}
            </td>
            <td class="px-6 py-4 hidden sm:table-cell align-top text-rose-400 font-mono text-xs">
                $${formatNumber(stop, 2)}
            </td>
            <td class="px-6 py-4 text-right align-top">
                <div class="flex flex-col items-end gap-2">
                    ${sparkline ? `<div class="w-[120px] h-[40px] inline-block">${sparkline}</div>` : ""}
                    <a href="${tradingViewUrl}" target="_blank" rel="noopener"
                       class="inline-flex items-center text-[11px] font-medium text-amber-400 hover:text-amber-300">
                        Voir &rarr;
                    </a>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", rowHtml);

    // Carte mobile
    if (cardContainer) {
        const badgeClass =
            variant === "phoenix"
                ? "bg-amber-500/10 text-amber-300 border border-amber-400/40"
                : "bg-emerald-500/10 text-emerald-300 border border-emerald-400/40";

        const cardHtml = `
            <article class="bg-slate-950/90 border border-slate-800/80 rounded-2xl p-4 flex flex-col gap-3 shadow-md">
                <div class="flex items-center justify-between gap-2">
                    <div>
                        <div class="font-semibold text-slate-100 text-sm">${name}</div>
                        <div class="text-[11px] text-slate-500 mt-0.5">${ticker}</div>
                    </div>
                    <span class="text-[11px] px-2 py-0.5 rounded-full ${badgeClass}">
                        ${variant === "phoenix" ? "Breakout" : "Pullback"}
                    </span>
                </div>

                <div class="text-[11px] text-slate-400 flex flex-col gap-1">
                    <span>${trendText}</span>
                    <span>Vol moyen 20j : ${volText}</span>
                </div>

                <div class="grid grid-cols-2 gap-3 text-[11px]">
                    <div>
                        <div class="uppercase tracking-wide text-slate-500">Score</div>
                        <div class="mt-0.5 font-mono ${scoreColor}">${score.toFixed(1)}</div>
                    </div>
                    <div>
                        <div class="uppercase tracking-wide text-slate-500">RSI</div>
                        <div class="mt-0.5 font-mono ${rsiColor}">${typeof rsi === "number" ? rsi.toFixed(1) : "-"}</div>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-3 text-[11px]">
                    <div>
                        <div class="uppercase tracking-wide text-slate-500">Prix</div>
                        <div class="mt-0.5 font-mono text-slate-100">$${formatNumber(price, 2)}</div>
                    </div>
                    <div>
                        <div class="uppercase tracking-wide text-slate-500">Stop</div>
                        <div class="mt-0.5 font-mono text-rose-400">$${formatNumber(stop, 2)}</div>
                    </div>
                </div>

                <div class="flex items-end justify-between gap-3">
                    ${sparkline ? `<div class="w-[120px] h-[40px]">${sparkline}</div>` : ""}
                    <a href="${tradingViewUrl}" target="_blank" rel="noopener"
                       class="inline-flex items-center text-[11px] font-medium text-amber-300 hover:text-amber-200">
                        Voir sur TradingView &rarr;
                    </a>
                </div>
            </article>
        `;
        cardContainer.insertAdjacentHTML("beforeend", cardHtml);
    }
}

async function loadSp500Phoenix() {
    const dateEl = document.getElementById("date-phoenix");
    const tbody = document.getElementById("table-phoenix");
    const cardsContainer = document.getElementById("cards-phoenix");
    const heroCountEl = document.getElementById("hero-phoenix-count");

    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Chargement des données...</td></tr>';
    if (cardsContainer) {
        cardsContainer.innerHTML = '<p class="text-xs text-slate-500 text-center">Chargement des données...</p>';
    }
    if (heroCountEl) heroCountEl.textContent = "–";

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
        if (cardsContainer) cardsContainer.innerHTML = "";

        if (!entries.length) {
            const emptyHtml = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Aucun breakout détecté aujourd\'hui.</td></tr>';
            tbody.innerHTML = emptyHtml;
            if (cardsContainer) {
                cardsContainer.innerHTML = '<p class="text-xs text-slate-500 text-center">Aucun breakout détecté aujourd\'hui.</p>';
            }
            if (heroCountEl) heroCountEl.textContent = "0";
            return;
        }

        entries.forEach(([ticker, info]) => {
            appendSignalRow(tbody, ticker, info, {
                variant: "phoenix",
                cardContainer: cardsContainer
            });
        });

        if (heroCountEl) {
            heroCountEl.textContent = String(entries.length);
        }
    } catch (error) {
        console.error("Erreur chargement S&P 500 Phoenix :", error);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-rose-400">Erreur lors du chargement des données.</td></tr>';
        if (cardsContainer) {
            cardsContainer.innerHTML = '<p class="text-xs text-rose-400 text-center">Erreur lors du chargement des données.</p>';
        }
        if (dateEl) {
            dateEl.textContent = "-";
        }
        if (heroCountEl) {
            heroCountEl.textContent = "–";
        }
    }
}

async function loadSp500Pullback() {
    const dateEl = document.getElementById("date-pullback");
    const tbody = document.getElementById("table-pullback");
    const cardsContainer = document.getElementById("cards-pullback");
    const heroCountEl = document.getElementById("hero-pullback-count");

    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Chargement des données...</td></tr>';
    if (cardsContainer) {
        cardsContainer.innerHTML = '<p class="text-xs text-slate-500 text-center">Chargement des données...</p>';
    }
    if (heroCountEl) heroCountEl.textContent = "–";

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
        if (cardsContainer) cardsContainer.innerHTML = "";

        if (!entries.length) {
            const emptyHtml = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Aucun pullback haussier détecté aujourd\'hui.</td></tr>';
            tbody.innerHTML = emptyHtml;
            if (cardsContainer) {
                cardsContainer.innerHTML = '<p class="text-xs text-slate-500 text-center">Aucun pullback haussier détecté aujourd\'hui.</p>';
            }
            if (heroCountEl) heroCountEl.textContent = "0";
            return;
        }

        entries.forEach(([ticker, info]) => {
            appendSignalRow(tbody, ticker, info, {
                variant: "pullback",
                cardContainer: cardsContainer
            });
        });

        if (heroCountEl) {
            heroCountEl.textContent = String(entries.length);
        }
    } catch (error) {
        console.error("Erreur chargement S&P 500 Pullback :", error);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-rose-400">Erreur lors du chargement des données.</td></tr>';
        if (cardsContainer) {
            cardsContainer.innerHTML = '<p class="text-xs text-rose-400 text-center">Erreur lors du chargement des données.</p>';
        }
        if (dateEl) {
            dateEl.textContent = "-";
        }
        if (heroCountEl) {
            heroCountEl.textContent = "–";
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadSp500Phoenix();
    loadSp500Pullback();
});

// assets/js/sp500.js
// Logique spécifique à la page S&P 500 (index.html)
// Dépendances : shared.js (createSparkline, formatNumber, getScoreColor, getRsiColor, loadSignalsData)

// Couleurs pour les avatars des tickers
const AVATAR_COLORS = [
    { bg: 'from-green-400/20 to-emerald-600/20', border: 'border-green-500/20', text: 'text-green-400' },
    { bg: 'from-blue-400/20 to-indigo-600/20', border: 'border-blue-500/20', text: 'text-blue-400' },
    { bg: 'from-orange-400/20 to-red-600/20', border: 'border-orange-500/20', text: 'text-orange-400' },
    { bg: 'from-purple-400/20 to-pink-600/20', border: 'border-purple-500/20', text: 'text-purple-400' },
    { bg: 'from-cyan-400/20 to-blue-600/20', border: 'border-cyan-500/20', text: 'text-cyan-400' },
    { bg: 'from-amber-400/20 to-yellow-600/20', border: 'border-amber-500/20', text: 'text-amber-400' },
    { bg: 'from-rose-400/20 to-pink-600/20', border: 'border-rose-500/20', text: 'text-rose-400' },
    { bg: 'from-teal-400/20 to-emerald-600/20', border: 'border-teal-500/20', text: 'text-teal-400' }
];

function getAvatarColor(ticker) {
    let hash = 0;
    for (let i = 0; i < ticker.length; i++) {
        hash = ticker.charCodeAt(i) + ((hash << 5) - hash);
    }
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

/**
 * Injecte une ligne dans un tbody HTML pour un signal donné
 * + une carte mobile si un conteneur mobile est fourni.
 */
function appendSignalRow(tbody, ticker, info, options) {
    const { variant, cardContainer } = options || {};

    const price = info.entry_price || 0;
    const stop = info.stop_loss || 0;
    const score = info.score || 0;
    const rsi = info.rsi;
    const volRatio = info.vol_ratio;
    const trendPct = info.trend_pct;
    const dollarVol = info.dollar_vol_avg20;
    const history = info.history || [];
    const name = info.name || ticker;

    const scoreColor = getScoreColor(score);
    const rsiColor = getRsiColor(rsi);
    const avatarColor = getAvatarColor(ticker);

    const volText =
        typeof volRatio === "number"
            ? `Vol x${volRatio.toFixed(1)} • $${formatNumber(dollarVol, 0)}`
            : `$${formatNumber(dollarVol, 0)} / jour`;

    const trendText =
        typeof trendPct === "number"
            ? (trendPct >= 0
                ? `+${trendPct.toFixed(1)}% vs SMA200`
                : `${trendPct.toFixed(1)}% vs SMA200`)
            : "n.d.";

    const sparklineColor = variant === "phoenix" ? "#fbbf24" : "#10b981";
    const scoreBarColor = variant === "phoenix" ? "score-bar-fill-amber" : "score-bar-fill-emerald";
    const sparkline = history && history.length > 1
        ? createSparkline(history, 120, 40, sparklineColor)
        : "";

    const tradingViewUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ticker)}`;

    // Ligne de tableau (desktop) - Premium Glass style
    const rowHtml = `
        <tr class="table-row-hover group">
            <td class="px-6 py-5">
                <div class="flex items-center gap-4">
                    <div class="w-12 h-12 rounded-2xl bg-gradient-to-br ${avatarColor.bg} ${avatarColor.border} border flex items-center justify-center">
                        <span class="font-bold ${avatarColor.text}">${ticker.charAt(0)}</span>
                    </div>
                    <div>
                        <p class="font-semibold text-white">${ticker}</p>
                        <p class="text-xs text-slate-500">${name}</p>
                    </div>
                </div>
            </td>
            <td class="px-6 py-5 hidden md:table-cell">
                <div class="flex flex-col gap-1">
                    <span class="text-sm font-medium ${variant === 'phoenix' ? 'text-amber-400' : 'text-emerald-400'}">${trendText}</span>
                    <span class="text-xs text-slate-500">${volText}</span>
                </div>
            </td>
            <td class="px-6 py-5">
                <div class="flex items-center gap-3">
                    <div class="w-20 h-2.5 score-bar">
                        <div class="score-bar-fill ${scoreBarColor}" style="width: ${Math.min(score, 100)}%"></div>
                    </div>
                    <span class="text-sm font-bold ${variant === 'phoenix' ? 'text-amber-400' : 'text-emerald-400'}">${score.toFixed(0)}</span>
                </div>
                <p class="text-xs text-slate-500 mt-1">RSI: <span class="${rsiColor}">${typeof rsi === "number" ? rsi.toFixed(1) : "-"}</span></p>
            </td>
            <td class="px-6 py-5 text-right font-medium hidden sm:table-cell">$${formatNumber(price, 2)}</td>
            <td class="px-6 py-5 text-right text-rose-400 hidden sm:table-cell">$${formatNumber(stop, 2)}</td>
            <td class="px-6 py-5 text-right">
                <div class="flex flex-col items-end gap-2">
                    ${sparkline ? `<div class="w-[120px] h-[40px]">${sparkline}</div>` : ""}
                    <a href="${tradingViewUrl}" target="_blank" rel="noopener"
                       class="btn-ghost">
                        TradingView →
                    </a>
                </div>
            </td>
        </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", rowHtml);

    // Carte mobile - Premium Glass style
    if (cardContainer) {
        const badgeClass = variant === "phoenix" ? "badge-phoenix" : "badge-pullback";

        const cardHtml = `
            <article class="glass-card-solid rounded-2xl p-4 flex flex-col gap-4">
                <div class="flex items-center justify-between gap-3">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-br ${avatarColor.bg} ${avatarColor.border} border flex items-center justify-center">
                            <span class="font-bold text-sm ${avatarColor.text}">${ticker.charAt(0)}</span>
                        </div>
                        <div>
                            <p class="font-semibold text-white text-sm">${ticker}</p>
                            <p class="text-[11px] text-slate-500">${name}</p>
                        </div>
                    </div>
                    <span class="badge ${badgeClass}">
                        ${variant === "phoenix" ? "Breakout" : "Pullback"}
                    </span>
                </div>

                <div class="flex items-center gap-3">
                    <div class="flex-1">
                        <div class="w-full h-2 score-bar">
                            <div class="score-bar-fill ${scoreBarColor}" style="width: ${Math.min(score, 100)}%"></div>
                        </div>
                    </div>
                    <span class="text-sm font-bold ${variant === 'phoenix' ? 'text-amber-400' : 'text-emerald-400'}">${score.toFixed(0)}</span>
                </div>

                <div class="grid grid-cols-2 gap-3 text-xs">
                    <div class="glass-card rounded-lg p-2">
                        <p class="text-[10px] text-slate-500 uppercase">Entrée</p>
                        <p class="font-medium text-slate-100">$${formatNumber(price, 2)}</p>
                    </div>
                    <div class="glass-card rounded-lg p-2">
                        <p class="text-[10px] text-slate-500 uppercase">Stop Loss</p>
                        <p class="font-medium text-rose-400">$${formatNumber(stop, 2)}</p>
                    </div>
                </div>

                <div class="flex items-end justify-between gap-3">
                    ${sparkline ? `<div class="w-[100px] h-[32px]">${sparkline}</div>` : '<div></div>'}
                    <a href="${tradingViewUrl}" target="_blank" rel="noopener"
                       class="text-xs font-medium ${variant === 'phoenix' ? 'text-amber-400' : 'text-emerald-400'}">
                        Voir sur TradingView →
                    </a>
                </div>
            </article>
        `;
        cardContainer.insertAdjacentHTML("beforeend", cardHtml);
    }
}

// Mise à jour des compteurs de badges
function updateBadgeCount(badgeId, count) {
    const badge = document.getElementById(badgeId);
    if (badge) {
        badge.textContent = `${count} signal${count > 1 ? 's' : ''}`;
    }
}

async function loadSp500Phoenix() {
    await loadSignalsData({
        url: "data/sp500_breakout_pro.json",
        dateElId: "date-phoenix",
        tbodyId: "table-phoenix",
        cardsContainerId: "cards-phoenix",
        heroCountElId: "hero-phoenix-count",
        variant: "phoenix",
        appendRow: appendSignalRow,
        emptyMessage: "Aucun breakout détecté aujourd'hui.",
        errorContext: "S&P 500 Phoenix"
    });

    // Mettre à jour le badge
    const count = document.getElementById("hero-phoenix-count")?.textContent;
    if (count && count !== "–") {
        updateBadgeCount("phoenix-count-badge", parseInt(count, 10));
    }
}

async function loadSp500Pullback() {
    await loadSignalsData({
        url: "data/sp500_pullback_pro.json",
        dateElId: "date-pullback",
        tbodyId: "table-pullback",
        cardsContainerId: "cards-pullback",
        heroCountElId: "hero-pullback-count",
        variant: "pullback",
        appendRow: appendSignalRow,
        emptyMessage: "Aucun pullback haussier détecté aujourd'hui.",
        errorContext: "S&P 500 Pullback"
    });

    // Mettre à jour le badge
    const count = document.getElementById("hero-pullback-count")?.textContent;
    if (count && count !== "–") {
        updateBadgeCount("pullback-count-badge", parseInt(count, 10));
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadSp500Phoenix();
    loadSp500Pullback();
});

// assets/js/sp500.js
// Logique spécifique à la page S&P 500 (index.html)
// Dépendances : shared.js (createSparkline, formatNumber, getScoreColor, getRsiColor, loadSignalsData)

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
}

document.addEventListener("DOMContentLoaded", () => {
    loadSp500Phoenix();
    loadSp500Pullback();
});

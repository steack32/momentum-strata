// assets/js/crypto.js
// Logique spécifique à la page Crypto (crypto.html)
// Dépendances : shared.js (createSparkline, formatNumber, getScoreColor, getRsiColor, loadSignalsData)

/**
 * Ajoute une ligne de signal crypto dans un tbody
 * + une carte mobile si un conteneur est fourni.
 */
function appendCryptoRow(tbody, symbol, info, options) {
    const { variant, cardContainer } = options || {};

    const price = info.entry_price || 0;
    const stop = info.stop_loss || 0;
    const score = info.score || 0;
    const rsi = info.rsi;
    const trendPct = info.trend_pct;
    const dollarVol = info.dollar_vol_avg20;
    const history = info.history || [];
    const name = info.name || symbol;

    const scoreColor = getScoreColor(score);
    const rsiColor = getRsiColor(rsi);

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

    // Ligne de tableau (desktop)
    const rowHtml = `
        <tr class="hover:bg-slate-800/50 border-b border-slate-800/50 transition-colors">
            <td class="px-6 py-4 align-top">
                <div class="font-bold text-slate-100 leading-snug">${name}</div>
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

    // Carte mobile
    if (cardContainer) {
        const badgeClass =
            variant === "phoenix"
                ? "bg-purple-500/10 text-purple-300 border border-purple-400/40"
                : "bg-emerald-500/10 text-emerald-300 border border-emerald-400/40";

        const cardHtml = `
            <article class="bg-slate-950/90 border border-slate-800/80 rounded-2xl p-4 flex flex-col gap-3 shadow-md">
                <div class="flex items-center justify-between gap-2">
                    <div>
                        <div class="font-semibold text-slate-100 text-sm">${name}</div>
                        <div class="text-[11px] text-slate-500 mt-0.5">${symbol}</div>
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
                        <div class="mt-0.5 font-mono text-slate-100">$${formatNumber(price, 4)}</div>
                    </div>
                    <div>
                        <div class="uppercase tracking-wide text-slate-500">Stop</div>
                        <div class="mt-0.5 font-mono text-rose-400">$${formatNumber(stop, 4)}</div>
                    </div>
                </div>

                <div class="flex items-end justify-between gap-3">
                    ${sparkline ? `<div class="w-[120px] h-[40px]">${sparkline}</div>` : ""}
                    <a href="${tradingViewUrl}" target="_blank" rel="noopener"
                       class="inline-flex items-center text-[11px] font-medium text-purple-300 hover:text-purple-200">
                        Voir sur TradingView &rarr;
                    </a>
                </div>
            </article>
        `;
        cardContainer.insertAdjacentHTML("beforeend", cardHtml);
    }
}

async function loadCryptoPhoenix() {
    await loadSignalsData({
        url: "data/crypto_breakout_pro.json",
        dateElId: "date-phoenix",
        tbodyId: "table-phoenix",
        cardsContainerId: "cards-crypto-phoenix",
        heroCountElId: "hero-crypto-phoenix-count",
        variant: "phoenix",
        appendRow: appendCryptoRow,
        emptyMessage: "Aucune opportunité haute qualité détectée aujourd'hui.",
        errorContext: "Crypto Phoenix"
    });
}

async function loadCryptoPullback() {
    await loadSignalsData({
        url: "data/crypto_pullback_pro.json",
        dateElId: "date-pullback",
        tbodyId: "table-pullback",
        cardsContainerId: "cards-crypto-pullback",
        heroCountElId: "hero-crypto-pullback-count",
        variant: "pullback",
        appendRow: appendCryptoRow,
        emptyMessage: "Aucune consolidation haussière détectée aujourd'hui.",
        errorContext: "Crypto Pullback"
    });
}

document.addEventListener("DOMContentLoaded", () => {
    loadCryptoPhoenix();
    loadCryptoPullback();
});

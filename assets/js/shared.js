// assets/js/shared.js
// Fonctions partagées entre les différentes pages du site

/**
 * Génère un mini-graphe (sparkline) en SVG à partir d'un tableau de prix.
 * @param {number[]} data - Tableau de valeurs numériques
 * @param {number} width - Largeur du SVG (default: 120)
 * @param {number} height - Hauteur du SVG (default: 40)
 * @param {string} color - Couleur de la ligne (default: "#10b981")
 * @returns {string} Code HTML du SVG
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

/**
 * Formate un nombre avec séparateurs de milliers et décimales.
 * @param {number} value - Valeur à formater
 * @param {number} digits - Nombre de décimales (default: 0)
 * @returns {string} Valeur formatée ou "-" si invalide
 */
function formatNumber(value, digits = 0) {
    if (value === null || value === undefined || isNaN(value)) return "-";
    return Number(value).toLocaleString("en-US", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
    });
}

/**
 * Retourne la classe CSS de couleur en fonction du score.
 * @param {number} score - Score entre 0 et 100
 * @returns {string} Classe Tailwind CSS
 */
function getScoreColor(score) {
    if (score >= 80) return "text-emerald-400";
    if (score >= 60) return "text-amber-300";
    return "text-slate-300";
}

/**
 * Retourne la classe CSS de couleur en fonction du RSI.
 * @param {number} rsi - Valeur RSI
 * @returns {string} Classe Tailwind CSS
 */
function getRsiColor(rsi) {
    if (typeof rsi === "number" && rsi > 70) return "text-rose-400";
    return "text-slate-300";
}

/**
 * Charge les données de signaux depuis un fichier JSON.
 * @param {Object} config - Configuration du chargement
 * @param {string} config.url - URL du fichier JSON
 * @param {string} config.dateElId - ID de l'élément pour afficher la date
 * @param {string} config.tbodyId - ID du tbody pour les données
 * @param {string} config.cardsContainerId - ID du conteneur de cartes (optionnel)
 * @param {string} config.heroCountElId - ID de l'élément pour le compteur hero
 * @param {string} config.variant - "phoenix" ou "pullback"
 * @param {Function} config.appendRow - Fonction pour ajouter une ligne
 * @param {string} config.emptyMessage - Message si aucune donnée
 * @param {string} config.errorContext - Contexte pour les logs d'erreur
 * @returns {Promise<void>}
 */
async function loadSignalsData(config) {
    const {
        url,
        dateElId,
        tbodyId,
        cardsContainerId,
        heroCountElId,
        variant,
        appendRow,
        emptyMessage,
        errorContext
    } = config;

    const dateEl = document.getElementById(dateElId);
    const tbody = document.getElementById(tbodyId);
    const cardsContainer = cardsContainerId ? document.getElementById(cardsContainerId) : null;
    const heroCountEl = heroCountElId ? document.getElementById(heroCountElId) : null;

    if (!tbody) return;

    // État de chargement
    tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">Chargement des données...</td></tr>';
    if (cardsContainer) {
        cardsContainer.innerHTML = '<p class="text-xs text-slate-500 text-center">Chargement des données...</p>';
    }
    if (heroCountEl) heroCountEl.textContent = "–";

    try {
        const response = await fetch(url);
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
            const emptyHtml = `<tr><td colspan="6" class="px-6 py-6 text-center text-xs text-slate-500">${emptyMessage}</td></tr>`;
            tbody.innerHTML = emptyHtml;
            if (cardsContainer) {
                cardsContainer.innerHTML = `<p class="text-xs text-slate-500 text-center">${emptyMessage}</p>`;
            }
            if (heroCountEl) heroCountEl.textContent = "0";
            return;
        }

        entries.forEach(([ticker, info]) => {
            appendRow(tbody, ticker, info, {
                variant: variant,
                cardContainer: cardsContainer
            });
        });

        if (heroCountEl) {
            heroCountEl.textContent = String(entries.length);
        }
    } catch (error) {
        console.error(`Erreur chargement ${errorContext} :`, error);
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

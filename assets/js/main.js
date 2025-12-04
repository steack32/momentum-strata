// assets/js/main.js

/**
 * Génère un mini-graphique SVG (Sparkline)
 * Cette fonction est maintenant globale et accessible par toutes les pages.
 */
window.createSparkline = function(data, width = 120, height = 40, color = "#10b981") {
    if (!data || data.length < 2) return '';
    
    const allValues = [...data];
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    
    // Si la ligne est plate, on évite la division par zéro
    const range = (max - min) === 0 ? 1 : max - min;
    
    const paddingY = 5;
    const effH = height - paddingY * 2;
    const stepX = width / (data.length - 1);

    const path = data.map((val, i) => {
        const x = i * stepX;
        // On inverse Y car en SVG le 0 est en haut
        const y = (height - paddingY) - ((val - min) / range * effH);
        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    return `
        <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" class="overflow-visible">
            <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
            <circle cx="${width}" cy="${(height - paddingY) - ((data[data.length-1] - min)/range * effH)}" r="2" fill="${color}" />
        </svg>
    `;
};

/**
 * Charge un composant HTML (Navbar/Footer) dans un élément cible
 */
async function loadComponent(elementId, filePath) {
    try {
        const response = await fetch(filePath);
        if (!response.ok) throw new Error(`Impossible de charger ${filePath}`);
        
        const htmlContent = await response.text();
        const element = document.getElementById(elementId);
        
        if (element) {
            element.innerHTML = htmlContent;
            
            // Si on vient de charger la navbar, on active le lien courant
            if (elementId === 'navbar-container') {
                highlightActiveLink();
            }
        }
    } catch (error) {
        console.error("Erreur de chargement du composant :", error);
    }
}

/**
 * Ajoute une classe visuelle au lien de navigation actif
 */
function highlightActiveLink() {
    const currentPath = window.location.pathname;
    const isCrypto = currentPath.includes('crypto');
    
    // Sélection des liens (suppose que vous avez respecté la structure donnée précédemment)
    const links = document.querySelectorAll('nav a');
    
    links.forEach(link => {
        const href = link.getAttribute('href');
        
        // Logique simple : Si on est sur crypto.html et que le lien pointe vers crypto.html
        if ((isCrypto && href.includes('crypto')) || (!isCrypto && (href === 'index.html' || href === './'))) {
            // On ajoute un style "actif" (ex: fond légèrement plus clair ou texte blanc brillant)
            link.classList.add('bg-slate-800', 'text-white', 'shadow-md');
            link.classList.remove('text-slate-300');
        }
    });
}

// Initialisation au chargement de la page
document.addEventListener("DOMContentLoaded", async () => {
    // Chargement parallèle de la navbar et du footer
    await Promise.all([
        loadComponent("navbar-container", "assets/components/navbar.html"),
        loadComponent("footer-container", "assets/components/footer.html")
    ]);
});
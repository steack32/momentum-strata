// assets/js/main.js

// Fonction générique pour charger un fichier HTML
async function loadComponent(elementId, filePath) {
    try {
        const response = await fetch(filePath);
        if (!response.ok) throw new Error(`Impossible de charger ${filePath}`);
        const htmlContent = await response.text();
        document.getElementById(elementId).innerHTML = htmlContent;
    } catch (error) {
        console.error("Erreur de chargement du composant :", error);
    }
}

// Lancement au chargement de la page
document.addEventListener("DOMContentLoaded", async () => {
    // 1. On attend le chargement complet de la Navbar et du Footer
    // Le "await" est important pour garantir l'ordre
    await Promise.all([
        loadComponent("navbar-container", "assets/components/navbar.html"),
        loadComponent("footer-container", "assets/components/footer.html")
    ]);

    // 2. IMPORTANT : On dit à Memberstack de rescanner la page
    // car de nouveaux boutons (login/logout) viennent d'apparaître
    if (window.$memberstackDom) {
        window.$memberstackDom.x.load();
    }
});
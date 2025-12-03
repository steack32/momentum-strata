// assets/js/main.js

// Fonction générique pour charger un fichier HTML dans un élément
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

// Exécution au chargement de la page
document.addEventListener("DOMContentLoaded", async () => {
    
    // 1. On charge Navbar et Footer en parallèle et on ATTEND la fin (await)
    await Promise.all([
        loadComponent("navbar-container", "assets/components/navbar.html"),
        loadComponent("footer-container", "assets/components/footer.html")
    ]);

    // 2. CRITIQUE : On dit à Memberstack de re-scanner la page
    // C'est indispensable car le bouton "Se déconnecter" vient d'être injecté par le JS ci-dessus.
    if (window.$memberstackDom) {
        window.$memberstackDom.x.load();
    }
});
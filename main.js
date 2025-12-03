// assets/js/main.js

// Fonction générique pour charger un fichier HTML dans un élément
async function loadComponent(elementId, filePath) {
    try {
        const response = await fetch(filePath);
        if (!response.ok) throw new Error(`Impossible de charger ${filePath}`);
        
        const htmlContent = await response.text();
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = htmlContent;
        }
    } catch (error) {
        console.error("Erreur de chargement du composant :", error);
    }
}

// Exécution au chargement de la page
document.addEventListener("DOMContentLoaded", async () => {
    
    // 1. On charge Navbar et Footer
    await Promise.all([
        loadComponent("navbar-container", "assets/components/navbar.html"),
        loadComponent("footer-container", "assets/components/footer.html")
    ]);

    // 2. CORRECTION SÉCURISÉE : On vérifie si Memberstack est prêt
    // On enlève le ".x" qui cause souvent des bugs
    if (window.$memberstackDom && window.$memberstackDom.load) {
        try {
            window.$memberstackDom.load();
        } catch (e) {
            console.log("Memberstack load warning:", e);
        }
    }
});
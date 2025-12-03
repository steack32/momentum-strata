// assets/js/main.js

// Fonction générique pour charger un fichier HTML
async function loadComponent(elementId, filePath) {
    try {
        const response = await fetch(filePath);
        if (!response.ok) throw new Error(`Impossible de charger ${filePath}`);
        const htmlContent = await response.text();
        const el = document.getElementById(elementId);
        if(el) el.innerHTML = htmlContent;
    } catch (error) {
        console.error(error);
    }
}

// Exécution au chargement
document.addEventListener("DOMContentLoaded", async () => {
    // 1. On charge juste la Navbar et le Footer
    await Promise.all([
        loadComponent("navbar-container", "assets/components/navbar.html"),
        loadComponent("footer-container", "assets/components/footer.html")
    ]);
});
// assets/js/main.js
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

document.addEventListener("DOMContentLoaded", async () => {
    // 1. On charge Navbar et Footer
    await Promise.all([
        loadComponent("navbar-container", "assets/components/navbar.html"),
        loadComponent("footer-container", "assets/components/footer.html")
    ]);

    // 2. IMPORTANT : On réveille Memberstack une fois le HTML injecté
    if (window.$memberstackDom) {
        window.$memberstackDom.x.load();
    }
});
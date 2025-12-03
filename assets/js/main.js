// assets/js/main.js

// Fonction simple pour charger un fichier HTML (Navbar/Footer)
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
    // Charge simplement la navbar et le footer
    await Promise.all([
        loadComponent("navbar-container", "assets/components/navbar.html"),
        loadComponent("footer-container", "assets/components/footer.html")
    ]);
});
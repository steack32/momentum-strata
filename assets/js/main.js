// assets/js/main.js

// Fonction générique pour charger un fichier HTML dans un élément
async function loadComponent(elementId, filePath) {
    try {
        // 1. On va chercher le fichier
        const response = await fetch(filePath);
        if (!response.ok) throw new Error(`Impossible de charger ${filePath}`);
        
        // 2. On récupère son contenu texte
        const htmlContent = await response.text();
        
        // 3. On injecte le contenu dans la boîte cible
        document.getElementById(elementId).innerHTML = htmlContent;
    } catch (error) {
        console.error("Erreur de chargement du composant :", error);
    }
}

// Quand la page a fini de charger sa structure de base...
document.addEventListener("DOMContentLoaded", () => {
    // ... on lance le chargement des composants
    // On cherche la boîte 'navbar-container' et on y met 'navbar.html'
    loadComponent("navbar-container", "assets/components/navbar.html");
    
    // On cherche la boîte 'footer-container' et on y met 'footer.html'
    loadComponent("footer-container", "assets/components/footer.html");
});
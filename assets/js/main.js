/**
 * Charge dynamiquement un composant HTML (navbar, footer…)
 */
async function loadComponent(containerId, componentPath) {
    try {
        const response = await fetch(componentPath);
        if (!response.ok) {
            console.error(`Erreur lors du chargement du composant : ${componentPath}`);
            return;
        }
        const html = await response.text();
        document.getElementById(containerId).innerHTML = html;
    } catch (error) {
        console.error("Erreur fetch composant :", error);
    }
}

/**
 * Active la bonne entrée de la navbar selon la page courante.
 */
function activateNavLink() {
    const current = window.location.pathname.split("/").pop() || "index.html";

    document.querySelectorAll(".nav-link").forEach(link => {
        if (link.getAttribute("href") === current) {
            link.classList.add("active");
        }
    });
}

/**
 * Initialise le menu mobile (ouverture/fermeture).
 */
function setupMobileMenu() {
    const btn = document.getElementById("mobile-menu-btn");
    const menu = document.getElementById("mobile-menu");

    if (!btn || !menu) return;

    btn.addEventListener("click", () => {
        menu.classList.toggle("hidden");
    });
}

/**
 * Initialisation générale une fois que tout est injecté.
 */
async function initSite() {
    // Injecte navbar + footer AVANT d'exécuter la logique qui dépend du DOM
    await Promise.all([
        loadComponent("navbar-container", "assets/components/navbar.html"),
        loadComponent("footer-container", "assets/components/footer.html"),
    ]);

    // Une fois tout injecté → on applique les comportements
    activateNavLink();
    setupMobileMenu();
}

document.addEventListener("DOMContentLoaded", initSite);

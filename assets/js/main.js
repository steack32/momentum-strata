// assets/js/main.js

// Chargement asynchrone de composants HTML (navbar, footer)
async function loadComponent(elementId, filePath) {
    try {
        const response = await fetch(filePath);
        if (!response.ok) {
            throw new Error(`Impossible de charger ${filePath} (statut ${response.status})`);
        }
        const htmlContent = await response.text();
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = htmlContent;
        }
    } catch (error) {
        console.error("Erreur de chargement du composant :", error);
    }
}

// Met à jour l'état "actif" dans la navbar une fois qu'elle est injectée
function highlightActiveNavLink() {
    const navbar = document.getElementById("navbar-container");
    if (!navbar) return;

    const currentPath = window.location.pathname.split("/").pop() || "index.html";
    const links = navbar.querySelectorAll("a[href$='.html']");

    links.forEach(link => {
        const href = link.getAttribute("href");
        if (!href) return;
        const isActive = href === currentPath;

        if (isActive) {
            link.classList.add(
                "text-white",
                "bg-slate-900/60",
                "border",
                "border-slate-700"
            );
        }
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    await Promise.all([
        loadComponent("navbar-container", "assets/components/navbar.html"),
        loadComponent("footer-container", "assets/components/footer.html")
    ]);

    // On laisse un tick pour que le DOM se mette à jour, puis on marque le lien actif
    requestAnimationFrame(highlightActiveNavLink);
});


document.addEventListener("DOMContentLoaded", () => {

    // --- HIGHLIGHT DE LA PAGE ACTIVE ---
    const path = window.location.pathname.split("/").pop();

    document.querySelectorAll(".nav-link").forEach(link => {
        if (link.getAttribute("href") === path) {
            link.classList.add("active");
        }
    });

    // --- MENU MOBILE ---
    const btn = document.getElementById("mobile-menu-btn");
    const mobileMenu = document.getElementById("mobile-menu");

    if (btn && mobileMenu) {
        btn.addEventListener("click", () => {
            mobileMenu.classList.toggle("hidden");
        });
    }

});


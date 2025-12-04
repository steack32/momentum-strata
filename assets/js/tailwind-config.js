// assets/js/tailwind-config.js

tailwind.config = {
    theme: {
        extend: {
            fontFamily: {
                // Définit 'Inter' comme police par défaut pour tout le site
                sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
            },
            colors: {
                // Vous pouvez définir ici des couleurs "marque" si vous voulez
                // Exemple : 'brand-blue': '#3b82f6',
                // Mais pour l'instant, nous utilisons les couleurs standard Tailwind (slate, blue, purple, amber, emerald)
            },
            boxShadow: {
                // Une ombre douce pour les tableaux (optionnel, style "premium")
                'premium': '0 4px 6px -1px rgba(0, 0, 0, 0.5), 0 2px 4px -1px rgba(0, 0, 0, 0.3)',
            }
        }
    }
}
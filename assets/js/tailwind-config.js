// assets/js/tailwind-config.js
tailwind.config = {
    theme: {
        extend: {
            colors: {
                brand: { 
                    dark: '#020617',      // slate-950
                    primary: '#2563eb',   // blue-600
                    accent: '#1d4ed8',    // blue-700
                    light: '#f8fafc',     // slate-50
                    surface: '#ffffff'
                }
            },
            fontFamily: { sans: ['Inter', 'sans-serif'] },
            boxShadow: {
                'premium': '0 10px 25px -15px rgba(15,23,42,0.35)',
                'soft': '0 6px 18px rgba(15,23,42,0.08)'
            }
        }
    }
}
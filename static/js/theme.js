/* =========================================================
   FileLabs — theme.js
   Dark mode : appliqué avant le premier rendu pour éviter le flash
   ========================================================= */
(function () {
  const STORAGE_KEY  = 'filelabs-theme';
  const VERSION_KEY  = 'filelabs-theme-v';
  const CURRENT_VER  = '2'; // incrémenter si le défaut change à nouveau

  // Migration : si l'utilisateur n'a pas encore vu la v2, on efface
  // l'ancien choix pour repartir sur le nouveau défaut (light/cream).
  if (localStorage.getItem(VERSION_KEY) !== CURRENT_VER) {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.setItem(VERSION_KEY, CURRENT_VER);
  }

  function getPreferred() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') return saved;
    // Default: light (cream palette); respect system dark mode if explicitly set
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }

  // Appliquer immédiatement (avant paint)
  apply(getPreferred());

  // Exposer pour le bouton toggle
  window.__theme = {
    get: () => document.documentElement.getAttribute('data-theme') || 'light',
    toggle: () => apply(window.__theme.get() === 'dark' ? 'light' : 'dark'),
  };

  // Met à jour les icônes lune/soleil après chaque toggle
  window.updateThemeIcon = function () {
    var dark = window.__theme.get() === 'dark';
    var moon = document.getElementById('iconMoon');
    var sun  = document.getElementById('iconSun');
    if (moon) moon.style.display = dark ? 'none' : '';
    if (sun)  sun.style.display  = dark ? '' : 'none';
  };

  // Appliquer au chargement initial (le DOM n'est pas encore prêt ici,
  // donc on diffère après DOMContentLoaded)
  document.addEventListener('DOMContentLoaded', window.updateThemeIcon);
})();

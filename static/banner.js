/* Bannière et adaptations affichées uniquement sur la version en ligne (non-localhost) */
(function () {
  const h = location.hostname;
  const isLocal = h === '' || h === 'localhost' || h === '127.0.0.1' || h === '::1' || h.startsWith('192.168.') || h.startsWith('10.');
  if (isLocal) return;

  // ── Bannière d'avertissement (non-dismissable : réapparaît à chaque page) ──
  const banner = document.createElement('div');
  banner.className = 'online-banner';
  banner.innerHTML = `
    <span>⚠️ Version en ligne : vos fichiers transitent par notre serveur et sont supprimés après 1h.</span>
    <a href="https://github.com/Enzo0673/filelabs/releases/latest" target="_blank" rel="noopener">
      ↓ Télécharger l'app locale (100% privé)
    </a>
  `;

  document.body.insertBefore(banner, document.body.firstChild);
  requestAnimationFrame(() => {
    document.body.style.paddingTop = banner.offsetHeight + 'px';
  });

  // ── Adapter le footer des pages outils ──
  document.querySelectorAll('.footer').forEach(f => {
    if (f.textContent.includes('100% local') || f.textContent.includes('ne quittent jamais')) {
      f.textContent = 'Fichiers supprimés automatiquement après 1h — aucune conservation longue durée';
    }
  });
})();

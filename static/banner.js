/* Bannière affichée uniquement sur la version en ligne (non-localhost) */
(function () {
  const h = location.hostname;
  const isLocal = h === '' || h === 'localhost' || h === '127.0.0.1' || h === '::1' || h.startsWith('192.168.') || h.startsWith('10.');
  if (isLocal) return;
  if (sessionStorage.getItem('banner-dismissed')) return;

  const banner = document.createElement('div');
  banner.className = 'online-banner';
  banner.innerHTML = `
    <span>⚠️ Version en ligne : vos fichiers transitent par notre serveur et sont supprimés après 1h.</span>
    <a href="https://github.com/Enzo0673/compressit/releases/latest" target="_blank" rel="noopener">
      ↓ Télécharger l'app locale (100% privé)
    </a>
    <button class="online-banner-close" aria-label="Fermer">✕</button>
  `;
  banner.querySelector('.online-banner-close').addEventListener('click', () => {
    document.body.style.paddingTop = '';
    banner.remove();
    sessionStorage.setItem('banner-dismissed', '1');
  });

  document.body.insertBefore(banner, document.body.firstChild);
  // Décaler le contenu pour ne pas être caché sous la bannière fixe
  requestAnimationFrame(() => {
    document.body.style.paddingTop = banner.offsetHeight + 'px';
  });
})();

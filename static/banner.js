/* Bannière affichée uniquement sur la version en ligne (non-localhost) */
(function () {
  const isLocal = ['localhost', '127.0.0.1', '::1'].includes(location.hostname);
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
    banner.remove();
    sessionStorage.setItem('banner-dismissed', '1');
  });

  document.body.insertBefore(banner, document.body.firstChild);
})();

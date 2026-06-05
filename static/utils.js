/* FileLab — utils.js : fonctions partagées entre tous les outils */

const FILE_SIZE_LIMITS = {
  pdf:     32 * 1024 * 1024,
  image:   32 * 1024 * 1024,
  video:  500 * 1024 * 1024,
  archive: 200 * 1024 * 1024,
};

const FILE_TYPE_MAP = {
  pdf: 'pdf',
  jpg: 'image', jpeg: 'image', png: 'image', webp: 'image',
  gif: 'image', bmp: 'image', tiff: 'image', tif: 'image',
  mp4: 'video', mov: 'video', avi: 'video', mkv: 'video', webm: 'video', m4v: 'video',
  zip: 'archive', '7z': 'archive', rar: 'archive', gz: 'archive',
  tar: 'archive', bz2: 'archive', zst: 'archive', xz: 'archive',
};

function getFileType(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  return FILE_TYPE_MAP[ext] || 'archive';
}

/**
 * Vérifie la taille d'un fichier avant envoi.
 * Retourne un message d'erreur si dépassé, null sinon.
 */
function checkFileSize(file, typeOverride) {
  const type = typeOverride || getFileType(file.name);
  const limit = FILE_SIZE_LIMITS[type] || FILE_SIZE_LIMITS.archive;
  if (file.size > limit) {
    const mb = Math.round(limit / 1024 / 1024);
    return `Fichier trop volumineux (max ${mb} Mo pour ce type de fichier)`;
  }
  return null;
}

/**
 * Désactive un bouton pendant le traitement async pour éviter le double-submit.
 */
function withButtonLock(btn, asyncFn) {
  return async function(...args) {
    if (btn.disabled) return;
    btn.disabled = true;
    btn.style.opacity = '0.6';
    btn.style.cursor = 'not-allowed';
    try {
      await asyncFn(...args);
    } finally {
      btn.disabled = false;
      btn.style.opacity = '';
      btn.style.cursor = '';
    }
  };
}

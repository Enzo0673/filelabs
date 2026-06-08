/* =========================================================
   FileLabs — home.js
   - Drag & drop global : affiche les outils compatibles avec le fichier déposé
   - Historique des outils récents (localStorage)
   ========================================================= */

(function () {

  // ── Outils par extension ───────────────────────────────────────────────────
  const EXT_TOOLS = {
    pdf:  [
      { path: '/tool/compress-pdf',      icon: '📦', name: 'Compresser PDF' },
      { path: '/tool/merge-pdf',         icon: '🔗', name: 'Fusionner PDF' },
      { path: '/tool/split-pdf',         icon: '✂️', name: 'Diviser PDF' },
      { path: '/tool/pdf-to-jpg',        icon: '🖼️', name: 'PDF vers JPG' },
      { path: '/tool/rotate-pdf',        icon: '🔄', name: 'Rotation PDF' },
      { path: '/tool/watermark-pdf',     icon: '💧', name: 'Filigrane PDF' },
      { path: '/tool/page-numbers-pdf',  icon: '🔢', name: 'Numéroter pages' },
      { path: '/tool/delete-pages-pdf',  icon: '🗑️', name: 'Supprimer pages' },
      { path: '/tool/unlock-pdf',        icon: '🔓', name: 'Déverrouiller PDF' },
      { path: '/tool/protect-pdf',       icon: '🔒', name: 'Protéger PDF' },
      { path: '/tool/repair-pdf',        icon: '🔧', name: 'Réparer PDF' },
      { path: '/tool/extract-text-pdf',  icon: '📝', name: 'Extraire texte' },
    ],
    jpg:  [
      { path: '/tool/compress-image', icon: '📦', name: 'Compresser image' },
      { path: '/tool/resize-image',   icon: '📐', name: 'Redimensionner' },
      { path: '/tool/convert-image',  icon: '🔁', name: 'Convertir format' },
      { path: '/tool/crop-image',     icon: '✂️', name: 'Recadrer' },
      { path: '/tool/rotate-image',   icon: '🔄', name: 'Rotation / Flip' },
      { path: '/tool/jpg-to-pdf',     icon: '📄', name: 'JPG vers PDF' },
    ],
    mp4:  [
      { path: '/tool/compress-video', icon: '🎬', name: 'Compresser vidéo' },
      { path: '/tool/edit-video',     icon: '✂️', name: 'Éditer vidéo' },
    ],
    zip:  [
      { path: '/tool/compress-archive', icon: '📦', name: 'Compresser archive' },
    ],
    docx: [
      { path: '/tool/office-to-pdf', icon: '📄', name: 'Word → PDF' },
    ],
    xlsx: [
      { path: '/tool/office-to-pdf', icon: '📄', name: 'Excel → PDF' },
    ],
    pptx: [
      { path: '/tool/office-to-pdf', icon: '📄', name: 'PowerPoint → PDF' },
    ],
  };

  // Alias
  const ALIAS = {
    jpeg: 'jpg', png: 'jpg', webp: 'jpg', gif: 'jpg', bmp: 'jpg', tiff: 'jpg', tif: 'jpg',
    mov: 'mp4', avi: 'mp4', mkv: 'mp4', webm: 'mp4',
    '7z': 'zip', rar: 'zip', tar: 'zip', gz: 'zip', bz2: 'zip', zst: 'zip',
    doc: 'docx', xls: 'xlsx', ppt: 'pptx',
    odt: 'docx', ods: 'xlsx', odp: 'pptx',
  };

  function getExt(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    return ALIAS[ext] || ext;
  }

  function getTools(ext) {
    return EXT_TOOLS[ext] || [];
  }

  // ── Overlay drag ───────────────────────────────────────────────────────────
  const overlay = document.createElement('div');
  overlay.id = 'drop-overlay';
  overlay.innerHTML = `
    <div class="drop-overlay-inner">
      <svg width="56" height="56" viewBox="0 0 64 64" fill="none">
        <path d="M32 12V44M32 12L20 24M32 12L44 24" stroke="#6366f1" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M12 52H52" stroke="#6366f1" stroke-width="4" stroke-linecap="round"/>
      </svg>
      <p class="drop-overlay-title">Déposez votre fichier</p>
      <p class="drop-overlay-sub" id="dropOverlaySub">Relâchez pour choisir un outil</p>
    </div>
  `;
  document.body.appendChild(overlay);

  // ── Modal de sélection d'outil ─────────────────────────────────────────────
  const modal = document.createElement('div');
  modal.id = 'tool-picker-modal';
  modal.innerHTML = `
    <div class="tool-picker-box">
      <div class="tool-picker-header">
        <span class="tool-picker-filename" id="pickerFilename"></span>
        <button class="tool-picker-close" id="pickerClose">✕</button>
      </div>
      <p class="tool-picker-label">Choisissez un outil</p>
      <div class="tool-picker-grid" id="pickerGrid"></div>
    </div>
  `;
  document.body.appendChild(modal);

  document.getElementById('pickerClose').addEventListener('click', () => {
    modal.classList.remove('active');
  });
  modal.addEventListener('click', e => {
    if (e.target === modal) modal.classList.remove('active');
  });

  function showPicker(file, tools) {
    document.getElementById('pickerFilename').textContent = file.name;
    const grid = document.getElementById('pickerGrid');
    grid.innerHTML = '';
    tools.forEach(t => {
      const btn = document.createElement('a');
      btn.className = 'tool-picker-item';
      btn.href = t.path;
      btn.innerHTML = `<span class="tool-picker-icon">${t.icon}</span><span class="tool-picker-name">${t.name}</span>`;
      grid.appendChild(btn);
    });
    modal.classList.add('active');
  }

  // ── Drag & drop ────────────────────────────────────────────────────────────
  let dragCounter = 0;

  document.addEventListener('dragenter', e => {
    if (!e.dataTransfer.types.includes('Files')) return;
    dragCounter++;
    const items = Array.from(e.dataTransfer.items || []);
    const item = items.find(i => i.kind === 'file');
    if (item) {
      const f = item.getAsFile?.();
      const ext = f ? getExt(f.name) : '';
      const tools = getTools(ext);
      document.getElementById('dropOverlaySub').textContent =
        tools.length > 0 ? `${tools.length} outil${tools.length > 1 ? 's' : ''} disponible${tools.length > 1 ? 's' : ''}` : 'Relâchez pour choisir un outil';
    }
    overlay.classList.add('active');
  });

  document.addEventListener('dragleave', e => {
    dragCounter--;
    if (dragCounter <= 0) { dragCounter = 0; overlay.classList.remove('active'); }
  });

  window.addEventListener('dragover', e => e.preventDefault(), false);
  window.addEventListener('drop', e => e.preventDefault(), false);
  document.addEventListener('dragover', e => e.preventDefault());

  document.addEventListener('drop', e => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter = 0;
    overlay.classList.remove('active');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const ext = getExt(file.name);
    const tools = getTools(ext);
    if (tools.length === 1) {
      window.location.href = tools[0].path;
    } else if (tools.length > 1) {
      showPicker(file, tools);
    } else {
      showToast(`Format .${file.name.split('.').pop()} non reconnu — choisissez un outil manuellement`);
    }
  });

  function showToast(msg) {
    const t = document.createElement('div');
    t.className = 'home-toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.classList.add('visible'), 10);
    setTimeout(() => { t.classList.remove('visible'); setTimeout(() => t.remove(), 300); }, 3000);
  }

  // ── Historique des outils récents ──────────────────────────────────────────
  const HISTORY_KEY = 'filelabs-history';
  const MAX_HISTORY = 5;

  function getHistory() {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); }
    catch { return []; }
  }

  function saveToHistory(toolPath, toolName, toolIcon) {
    let h = getHistory().filter(x => x.path !== toolPath);
    h.unshift({ path: toolPath, name: toolName, icon: toolIcon, ts: Date.now() });
    h = h.slice(0, MAX_HISTORY);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(h));
  }

  document.querySelectorAll('.tool-card[href]').forEach(card => {
    card.addEventListener('click', () => {
      const path = card.getAttribute('href');
      const name = card.querySelector('.tool-name')?.textContent || path;
      const icon = card.querySelector('.tool-icon')?.textContent || '🔧';
      saveToHistory(path, name, icon);
    });
  });

  function renderHistory() {
    const h = getHistory();
    if (h.length === 0) return;

    const section = document.createElement('section');
    section.className = 'tool-section history-section';
    section.innerHTML = `
      <div class="section-header">
        <span class="section-icon" style="background:#f1f5f9">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="7" stroke="#64748b" stroke-width="1.5" fill="none"/>
            <path d="M10 6v4l3 2" stroke="#64748b" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </span>
        <h2 class="section-title" style="color:var(--text-muted);font-size:1rem">Récents</h2>
        <button id="clearHistory" style="margin-left:auto;background:none;border:none;color:var(--text-muted);font-size:0.8rem;cursor:pointer;opacity:0.6">Effacer</button>
      </div>
      <div class="tools-grid" id="historyGrid"></div>
    `;

    const grid = section.querySelector('#historyGrid');
    h.forEach(item => {
      const card = document.createElement('a');
      card.className = 'tool-card';
      card.href = item.path;
      card.innerHTML = `<span class="tool-icon">${item.icon}</span><span class="tool-name">${item.name}</span>`;
      card.addEventListener('click', () => saveToHistory(item.path, item.name, item.icon));
      grid.appendChild(card);
    });

    section.querySelector('#clearHistory').addEventListener('click', e => {
      e.preventDefault();
      localStorage.removeItem(HISTORY_KEY);
      section.remove();
    });

    const firstSection = document.querySelector('.tool-section');
    if (firstSection) firstSection.parentNode.insertBefore(section, firstSection);
  }

  renderHistory();

})();

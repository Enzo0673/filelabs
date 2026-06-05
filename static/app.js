/* =========================================================
   FileLab — app.js
   ========================================================= */

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

const dropZone     = document.getElementById('dropZone');
const fileInput    = document.getElementById('fileInput');
const configPanel  = document.getElementById('configPanel');
const progressPanel = document.getElementById('progressPanel');
const resultPanel  = document.getElementById('resultPanel');
const errorPanel   = document.getElementById('errorPanel');
const expertToggle = document.getElementById('expertToggle');
const expertPanel  = document.getElementById('expertPanel');
const expertArrow  = document.getElementById('expertArrow');
const btnCompress  = document.getElementById('btnCompress');
const btnDownload  = document.getElementById('btnDownload');
const btnReset     = document.getElementById('btnReset');
const btnErrorReset = document.getElementById('btnErrorReset');

let currentFile = null;
let currentDownloadId = null;
let selectedLevel = 'standard';

// ---- File type detection ----
const FILE_ICONS = {
  image:   '🖼️',
  video:   '🎬',
  pdf:     '📄',
  archive: '📦',
};

const EXT_TYPE = {
  jpg: 'image', jpeg: 'image', png: 'image', webp: 'image',
  gif: 'image', bmp: 'image', tiff: 'image', tif: 'image',
  pdf: 'pdf',
  mp4: 'video', mov: 'video', avi: 'video', mkv: 'video',
  webm: 'video', m4v: 'video', flv: 'video',
  zip: 'archive', '7z': 'archive', rar: 'archive',
  gz: 'archive', tar: 'archive', bz2: 'archive',
  zst: 'archive', lz4: 'archive', xz: 'archive',
};

function detectType(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  return EXT_TYPE[ext] || 'archive';
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' o';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' Ko';
  return (bytes / (1024 * 1024)).toFixed(2) + ' Mo';
}

// ---- Drag & Drop ----
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) loadFile(file);
});
dropZone.addEventListener('click', (e) => {
  if (e.target.closest('label')) return;
  fileInput.click();
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) loadFile(fileInput.files[0]);
});

// ---- Load file ----
function loadFile(file) {
  const sizeError = checkFileSize(file);
  if (sizeError) {
    document.getElementById('errorMsg').textContent = sizeError;
    showPanel(errorPanel);
    return;
  }
  currentFile = file;
  const type = detectType(file.name);

  // Preview
  document.getElementById('filePreview').innerHTML = `
    <span class="file-icon">${FILE_ICONS[type]}</span>
    <div class="file-info">
      <div class="file-name">${escapeHtml(file.name)}</div>
      <div class="file-size">${formatBytes(file.size)}</div>
    </div>
  `;

  // Afficher les options expertes du bon type
  document.getElementById('expertImage').hidden   = (type !== 'image');
  document.getElementById('expertVideo').hidden   = (type !== 'video');
  document.getElementById('expertPdf').hidden     = (type !== 'pdf');
  document.getElementById('expertArchive').hidden = (type !== 'archive');

  showPanel(configPanel);
}

// ---- Level buttons ----
document.querySelectorAll('.level-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.level-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedLevel = btn.dataset.level;
  });
});

// ---- Expert toggle ----
expertToggle.addEventListener('click', () => {
  const isOpen = !expertPanel.hidden;
  expertPanel.hidden = isOpen;
  expertToggle.classList.toggle('open', !isOpen);
  expertArrow.classList.toggle('rotated', !isOpen);
});

// ---- Progress bar animée ----
let _progressInterval = null;
let _progressES = null;

function startProgress(fileSizeBytes, fileType, jobId) {
  const bar = document.getElementById('progressBar');
  const elapsed = document.getElementById('progressElapsed');

  bar.style.animation = 'none';
  bar.style.transform = 'none';
  bar.style.width = '0%';
  bar.style.transition = 'none';

  if (fileType === 'video' && jobId) {
    let startTime = Date.now();
    const tick = setInterval(() => {
      elapsed.textContent = Math.floor((Date.now() - startTime) / 1000) + 's';
    }, 1000);
    _progressES = new EventSource(`/compress/progress/${jobId}`);
    _progressES.onmessage = e => {
      const pct = parseFloat(e.data);
      bar.style.transition = 'width 0.4s ease';
      bar.style.width = Math.min(pct, 99).toFixed(1) + '%';
      if (pct >= 100) { _progressES.close(); _progressES = null; clearInterval(tick); }
    };
    _progressES.onerror = () => { _progressES.close(); _progressES = null; clearInterval(tick); };
    _progressInterval = tick;
    return;
  }

  // Estimation classique
  const mbSize = fileSizeBytes / (1024 * 1024);
  const durations = { image: 800, pdf: 1500, video: mbSize * 1200, archive: mbSize * 600 };
  const estimatedMs = Math.max(1000, Math.min(durations[fileType] || mbSize * 800, 60000));
  let startTime = Date.now();
  _progressInterval = setInterval(() => {
    const t = (Date.now() - startTime) / estimatedMs;
    const pct = 95 * (1 - Math.exp(-3 * t));
    bar.style.width = pct.toFixed(1) + '%';
    elapsed.textContent = Math.floor((Date.now() - startTime) / 1000) + 's';
  }, 80);
}

function finishProgress() {
  clearInterval(_progressInterval);
  _progressInterval = null;
  if (_progressES) { _progressES.close(); _progressES = null; }
  const bar = document.getElementById('progressBar');
  bar.style.transition = 'width 0.3s ease';
  bar.style.width = '100%';
}
btnCompress.addEventListener('click', withButtonLock(btnCompress, async () => {
  if (!currentFile) return;

  const fileType = detectType(currentFile.name);
  const jobId = crypto.randomUUID().replace(/-/g, '');
  showPanel(progressPanel);
  startProgress(currentFile.size, fileType, fileType === 'video' ? jobId : null);

  const fd = new FormData();
  fd.append('file', currentFile);
  fd.append('level', selectedLevel);
  fd.append('job_id', jobId);

  // Options image
  const imgQ = document.getElementById('imgQuality').value;
  const imgFmt = document.getElementById('imgFormat').value;
  const imgW = document.getElementById('imgMaxWidth').value;
  if (imgQ) fd.append('img_quality', imgQ);
  if (imgFmt) fd.append('img_format', imgFmt);
  if (imgW) fd.append('img_max_width', imgW);

  // Options vidéo
  const vidCrf = document.getElementById('vidCrf').value;
  const vidCodec = document.getElementById('vidCodec').value;
  const vidPreset = document.getElementById('vidPreset').value;
  const vidH = document.getElementById('vidHeight').value;
  if (vidCrf) fd.append('vid_crf', vidCrf);
  if (vidCodec) fd.append('vid_codec', vidCodec);
  if (vidPreset) fd.append('vid_preset', vidPreset);
  if (vidH) fd.append('vid_max_height', vidH);

  // Options PDF
  const pdfDpi = document.getElementById('pdfDpi').value;
  const pdfMeta = document.getElementById('pdfMeta').checked;
  if (pdfDpi) fd.append('pdf_dpi', pdfDpi);
  fd.append('pdf_remove_metadata', pdfMeta ? 'true' : 'false');

  // Options archive
  const arcAlgo = document.getElementById('arcAlgo').value;
  const arcLvl = document.getElementById('arcLevel').value;
  if (arcAlgo) fd.append('arc_algo', arcAlgo);
  if (arcLvl) fd.append('arc_level', arcLvl);

  try {
    const res = await fetch('/compress', { method: 'POST', body: fd });
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || 'Erreur serveur');

    finishProgress();
    setTimeout(() => {
      currentDownloadId = data.download_id;
      showResult(data);
    }, 350);
  } catch (err) {
    finishProgress();
    console.error('Erreur compression:', err);
    showError(err.message);
  }
}));

// ---- Show result ----
function showResult(data) {
  document.getElementById('resultBadge').textContent = `−${data.gain_pct}%`;

  document.getElementById('resultStats').innerHTML = `
    <div class="stat-item">
      <span class="stat-label">Avant</span>
      <span class="stat-value">${formatBytes(data.original_size)}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Après</span>
      <span class="stat-value">${formatBytes(data.compressed_size)}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Gain</span>
      <span class="stat-value" style="color:var(--success)">−${formatBytes(data.original_size - data.compressed_size)}</span>
    </div>
  `;

  btnDownload.href = `/download/${data.download_id}`;
  btnDownload.download = data.output_filename;
  setTimeout(() => btnDownload.click(), 400);

  showPanel(resultPanel);
}

// ---- Show error ----
function showError(msg) {
  document.getElementById('errorMsg').textContent = msg;
  showPanel(errorPanel);
}

// ---- Reset ----
[btnReset, btnErrorReset].forEach(btn => btn.addEventListener('click', reset));

function reset() {
  if (currentDownloadId) {
    fetch(`/cleanup/${currentDownloadId}`, { method: 'DELETE' }).catch(() => {});
    currentDownloadId = null;
  }
  currentFile = null;
  fileInput.value = '';

  // Reset expert fields
  document.getElementById('imgQuality').value = '';
  document.getElementById('imgFormat').value = '';
  document.getElementById('imgMaxWidth').value = '';
  document.getElementById('vidCrf').value = '';
  document.getElementById('vidPreset').value = 'medium';
  document.getElementById('vidHeight').value = '';
  document.getElementById('pdfDpi').value = '';
  document.getElementById('pdfMeta').checked = true;
  document.getElementById('arcAlgo').value = '';
  document.getElementById('arcLevel').value = '';

  // Reset level
  document.querySelectorAll('.level-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('[data-level="standard"]').classList.add('active');
  selectedLevel = 'standard';

  // Fermer expert
  expertPanel.hidden = true;
  expertToggle.classList.remove('open');
  expertArrow.classList.remove('rotated');

  showPanel(dropZone);
}

// ---- Panel switcher ----
const ALL_PANELS = [dropZone, configPanel, progressPanel, resultPanel, errorPanel];
function showPanel(panel) {
  ALL_PANELS.forEach(p => {
    p.style.display = (p === panel) ? '' : 'none';
    p.hidden = (p !== panel);
  });
}

// Initialisation : afficher uniquement la drop zone
showPanel(dropZone);

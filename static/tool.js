/* =========================================================
   FileLab — tool.js
   Script commun à toutes les pages outils
   ========================================================= */

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function initTool(config) {
  const dropZone      = document.getElementById('dropZone');
  const fileInput     = document.getElementById('fileInput');
  const configPanel   = document.getElementById('configPanel');
  const progressPanel = document.getElementById('progressPanel');
  const resultPanel   = document.getElementById('resultPanel');
  const errorPanel    = document.getElementById('errorPanel');
  const btnCompress   = document.getElementById('btnCompress');
  const btnDownload   = document.getElementById('btnDownload');
  const btnReset      = document.getElementById('btnReset');
  const btnErrorReset = document.getElementById('btnErrorReset');
  const expertToggle  = document.getElementById('expertToggle');
  const expertPanel   = document.getElementById('expertPanel');
  const expertArrow   = document.getElementById('expertArrow');

  let currentFile = null;
  let currentDownloadId = null;
  let selectedLevel = 'standard';
  let _originalBlobUrl = null;

  const FILE_ICONS = { image: '🖼️', video: '🎬', pdf: '📄', archive: '📦' };
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
  if (dropZone) {
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) loadFile(file);
    });
    dropZone.addEventListener('click', e => {
      if (e.target.closest('label')) return;
      fileInput.click();
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) loadFile(fileInput.files[0]);
    });
  }

  function loadFile(file) {
    const sizeError = checkFileSize(file);
    if (sizeError) {
      const el = document.getElementById('errorMsg');
      if (el) el.textContent = sizeError;
      showPanel(errorPanel);
      return;
    }
    currentFile = file;
    const type = detectType(file.name);
    if (type === 'image') {
      if (_originalBlobUrl) URL.revokeObjectURL(_originalBlobUrl);
      _originalBlobUrl = URL.createObjectURL(file);
    }
    const preview = document.getElementById('filePreview');
    if (preview) {
      if (type === 'image') {
        const url = URL.createObjectURL(file);
        const img = new window.Image();
        img.onload = () => {
          preview.innerHTML = `
            <img src="${url}" alt="${escapeHtml(file.name)}" style="max-width:100%;max-height:160px;border-radius:8px;object-fit:contain;box-shadow:var(--shadow)" />
            <div class="file-info" style="margin-top:8px">
              <div class="file-name">${escapeHtml(file.name)}</div>
              <div class="file-size">${formatBytes(file.size)} — ${img.naturalWidth}×${img.naturalHeight} px</div>
            </div>
          `;
        };
        img.src = url;
      } else if (type === 'video') {
        const url = URL.createObjectURL(file);
        const video = document.createElement('video');
        video.src = url;
        video.preload = 'metadata';
        video.onloadedmetadata = () => {
          video.currentTime = Math.min(1, video.duration * 0.1);
        };
        video.onseeked = () => {
          const canvas = document.createElement('canvas');
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          canvas.getContext('2d').drawImage(video, 0, 0);
          const dur = video.duration ? `${Math.floor(video.duration / 60)}m${Math.floor(video.duration % 60)}s` : '';
          preview.innerHTML = `
            <img src="${canvas.toDataURL()}" alt="aperçu" style="max-width:100%;max-height:160px;border-radius:8px;object-fit:contain;box-shadow:var(--shadow)" />
            <div class="file-info" style="margin-top:8px">
              <div class="file-name">${escapeHtml(file.name)}</div>
              <div class="file-size">${formatBytes(file.size)}${dur ? ' — ' + dur : ''}</div>
            </div>
          `;
          URL.revokeObjectURL(url);
        };
      } else if (type === 'pdf') {
        const url = URL.createObjectURL(file);
        file.arrayBuffer().then(buf => {
          if (typeof pdfjsLib === 'undefined') {
            preview.innerHTML = `<span class="file-icon">📄</span><div class="file-info"><div class="file-name">${escapeHtml(file.name)}</div><div class="file-size">${formatBytes(file.size)}</div></div>`;
            return;
          }
          pdfjsLib.getDocument({ data: buf }).promise.then(pdf => {
            pdf.getPage(1).then(page => {
              const vp = page.getViewport({ scale: 0.4 });
              const canvas = document.createElement('canvas');
              canvas.width = vp.width; canvas.height = vp.height;
              page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise.then(() => {
                preview.innerHTML = '';
                canvas.style.cssText = 'border-radius:6px;box-shadow:var(--shadow);max-width:120px;height:auto;display:block';
                const info = document.createElement('div');
                info.className = 'file-info';
                info.style.marginTop = '8px';
                info.innerHTML = `<div class="file-name">${escapeHtml(file.name)}</div><div class="file-size">${formatBytes(file.size)} — ${pdf.numPages} page${pdf.numPages > 1 ? 's' : ''}</div>`;
                preview.style.flexDirection = 'column';
                preview.style.alignItems = 'flex-start';
                preview.appendChild(canvas);
                preview.appendChild(info);
              });
            });
          }).catch(() => {
            preview.innerHTML = `<span class="file-icon">📄</span><div class="file-info"><div class="file-name">${escapeHtml(file.name)}</div><div class="file-size">${formatBytes(file.size)}</div></div>`;
          });
          URL.revokeObjectURL(url);
        });
      } else {
        preview.innerHTML = `
          <span class="file-icon">${FILE_ICONS[type] || '📄'}</span>
          <div class="file-info">
            <div class="file-name">${escapeHtml(file.name)}</div>
            <div class="file-size">${formatBytes(file.size)}</div>
          </div>
        `;
      }
    }
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
  if (expertToggle && expertPanel) {
    expertToggle.addEventListener('click', () => {
      const isOpen = !expertPanel.hidden;
      expertPanel.hidden = isOpen;
      expertToggle.classList.toggle('open', !isOpen);
      if (expertArrow) expertArrow.classList.toggle('rotated', !isOpen);
    });
  }

  // ---- Progress bar ----
  let _progressInterval = null;
  let _progressES = null;

  function startProgress(fileSizeBytes, fileType, jobId) {
    const bar = document.getElementById('progressBar');
    const elapsed = document.getElementById('progressElapsed');
    bar.style.width = '0%';
    bar.style.transition = 'none';

    if (fileType === 'video' && jobId) {
      // Progression réelle via SSE
      let startTime = Date.now();
      const tick = setInterval(() => {
        if (elapsed) elapsed.textContent = Math.floor((Date.now() - startTime) / 1000) + 's';
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

    // Estimation classique pour les autres types
    const mbSize = fileSizeBytes / (1024 * 1024);
    const durations = { image: 800, pdf: 1500, video: mbSize * 1200, archive: mbSize * 600 };
    const estimatedMs = Math.max(1000, Math.min(durations[fileType] || mbSize * 800, 60000));
    let startTime = Date.now();
    _progressInterval = setInterval(() => {
      const t = (Date.now() - startTime) / estimatedMs;
      const pct = 95 * (1 - Math.exp(-3 * t));
      bar.style.width = pct.toFixed(1) + '%';
      if (elapsed) elapsed.textContent = Math.floor((Date.now() - startTime) / 1000) + 's';
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

  // ---- Compress ----
  if (btnCompress) {
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
      const imgQ = document.getElementById('imgQuality');
      const imgFmt = document.getElementById('imgFormat');
      const imgW = document.getElementById('imgMaxWidth');
      if (imgQ && imgQ.value) fd.append('img_quality', imgQ.value);
      if (imgFmt && imgFmt.value) fd.append('img_format', imgFmt.value);
      if (imgW && imgW.value) fd.append('img_max_width', imgW.value);

      // Options vidéo
      const vidCrf = document.getElementById('vidCrf');
      const vidCodec = document.getElementById('vidCodec');
      const vidPreset = document.getElementById('vidPreset');
      const vidH = document.getElementById('vidHeight');
      if (vidCrf && vidCrf.value) fd.append('vid_crf', vidCrf.value);
      if (vidCodec && vidCodec.value) fd.append('vid_codec', vidCodec.value);
      if (vidPreset && vidPreset.value) fd.append('vid_preset', vidPreset.value);
      if (vidH && vidH.value) fd.append('vid_max_height', vidH.value);

      // Options PDF
      const pdfDpi = document.getElementById('pdfDpi');
      const pdfMeta = document.getElementById('pdfMeta');
      if (pdfDpi && pdfDpi.value) fd.append('pdf_dpi', pdfDpi.value);
      if (pdfMeta) fd.append('pdf_remove_metadata', pdfMeta.checked ? 'true' : 'false');

      // Options archive
      const arcAlgo = document.getElementById('arcAlgo');
      const arcLvl = document.getElementById('arcLevel');
      if (arcAlgo && arcAlgo.value) fd.append('arc_algo', arcAlgo.value);
      if (arcLvl && arcLvl.value) fd.append('arc_level', arcLvl.value);

      try {
        const res = await fetch('/compress', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erreur serveur');
        finishProgress();
        setTimeout(() => { currentDownloadId = data.download_id; showResult(data); }, 350);
      } catch (err) {
        finishProgress();
        showError(err.message);
      }
    }));
  }

  // ---- Result ----
  function showResult(data) {
    document.getElementById('resultBadge').textContent = `−${data.gain_pct}%`;
    document.getElementById('resultStats').innerHTML = `
      <div class="stat-item"><span class="stat-label">Avant</span><span class="stat-value">${formatBytes(data.original_size)}</span></div>
      <div class="stat-item"><span class="stat-label">Après</span><span class="stat-value">${formatBytes(data.compressed_size)}</span></div>
      <div class="stat-item"><span class="stat-label">Gain</span><span class="stat-value" style="color:var(--success)">−${formatBytes(data.original_size - data.compressed_size)}</span></div>
    `;
    if (btnDownload) {
      btnDownload.href = `/download/${data.download_id}`;
      btnDownload.download = data.output_filename;
      setTimeout(() => btnDownload.click(), 400);
    }
    showPanel(resultPanel);
    if (data.file_type === 'image' && _originalBlobUrl) {
      _renderImageSlider(_originalBlobUrl, `/download/${data.download_id}`);
    }
  }

  function _renderImageSlider(originalUrl, compressedUrl) {
    document.getElementById('imageSlider')?.remove();
    const slider = document.createElement('div');
    slider.id = 'imageSlider';
    slider.className = 'image-slider';
    slider.innerHTML = `
      <div class="slider-wrap" id="sliderWrap">
        <img class="slider-img slider-img--compressed" src="${compressedUrl}" alt="Compressé" />
        <div class="slider-clip" id="sliderClip">
          <img class="slider-img slider-img--original" src="${originalUrl}" alt="Original" />
        </div>
        <div class="slider-divider" id="sliderDivider">
          <div class="slider-handle">⇔</div>
        </div>
      </div>
      <div class="slider-labels"><span>Original</span><span>Compressé</span></div>
      <input type="range" class="slider-range" id="sliderRange" min="0" max="100" value="50" />
    `;
    const actions = resultPanel.querySelector('.result-actions');
    resultPanel.insertBefore(slider, actions);

    const range = slider.querySelector('#sliderRange');
    const clip = slider.querySelector('#sliderClip');
    const divider = slider.querySelector('#sliderDivider');
    const wrap = slider.querySelector('#sliderWrap');

    function setPos(pct) {
      clip.style.width = pct + '%';
      divider.style.left = pct + '%';
      range.value = pct;
    }

    range.addEventListener('input', () => setPos(range.value));

    let dragging = false;
    divider.addEventListener('pointerdown', e => { dragging = true; divider.setPointerCapture(e.pointerId); });
    wrap.addEventListener('pointermove', e => {
      if (!dragging) return;
      const rect = wrap.getBoundingClientRect();
      setPos(Math.max(0, Math.min(100, (e.clientX - rect.left) / rect.width * 100)).toFixed(1));
    });
    wrap.addEventListener('pointerup', () => { dragging = false; });
  }

  // ---- Reset ----
  function reset() {
    if (currentDownloadId) {
      fetch(`/cleanup/${currentDownloadId}`, { method: 'DELETE' }).catch(() => {});
      currentDownloadId = null;
    }
    currentFile = null;
    if (_originalBlobUrl) { URL.revokeObjectURL(_originalBlobUrl); _originalBlobUrl = null; }
    document.getElementById('imageSlider')?.remove();
    if (fileInput) fileInput.value = '';
    showPanel(dropZone);
  }

  if (btnReset) btnReset.addEventListener('click', reset);
  if (btnErrorReset) btnErrorReset.addEventListener('click', reset);

  // ---- Panel switcher ----
  const ALL_PANELS = [dropZone, configPanel, progressPanel, resultPanel, errorPanel].filter(Boolean);
  function showPanel(panel) {
    ALL_PANELS.forEach(p => { p.style.display = (p === panel) ? '' : 'none'; p.hidden = (p !== panel); });
  }

  showPanel(dropZone);
}

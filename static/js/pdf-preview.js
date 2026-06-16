/* Helper partagé : prévisualisation PDF.js (première page) */
function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function renderPdfPreview(file, container, onPageCount) {
  const fallback = () => {
    container.innerHTML = `<span class="file-icon">📄</span><div class="file-info"><div class="file-name">${escapeHtml(file.name)}</div><div class="file-size">${(file.size < 1024*1024 ? (file.size/1024).toFixed(1)+' Ko' : (file.size/(1024*1024)).toFixed(2)+' Mo')}</div></div>`;
  };
  if (typeof pdfjsLib === 'undefined') { fallback(); return; }
  file.arrayBuffer().then(buf => {
    pdfjsLib.getDocument({ data: buf }).promise.then(pdf => {
      if (onPageCount) onPageCount(pdf.numPages);
      pdf.getPage(1).then(page => {
        const vp = page.getViewport({ scale: 0.4 });
        const canvas = document.createElement('canvas');
        canvas.width = vp.width; canvas.height = vp.height;
        page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise.then(() => {
          canvas.style.cssText = 'border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.12);max-width:120px;height:auto;display:block';
          const sizeStr = file.size < 1024*1024 ? (file.size/1024).toFixed(1)+' Ko' : (file.size/(1024*1024)).toFixed(2)+' Mo';
          container.style.cssText = 'display:flex;flex-direction:column;align-items:flex-start;gap:8px';
          container.innerHTML = '';
          container.appendChild(canvas);
          const info = document.createElement('div');
          info.className = 'file-info';
          info.innerHTML = `<div class="file-name">${escapeHtml(file.name)}</div><div class="file-size">${sizeStr} — ${pdf.numPages} page${pdf.numPages > 1 ? 's' : ''}</div>`;
          container.appendChild(info);
        });
      });
    }).catch(fallback);
  }).catch(fallback);
}

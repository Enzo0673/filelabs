/* =========================================================
   FileLabs — archive-processor.js
   Compression archives 100% côté client via fflate (CDN).
   Supporte : zip, gzip, deflate.
   ========================================================= */
(function () {
  'use strict';

  /* ---- loader CDN fflate ---- */
  var _ready = null;

  function loadFflate() {
    if (_ready) return _ready;
    _ready = new Promise(function (resolve, reject) {
      if (window.fflate) { resolve(window.fflate); return; }
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/fflate@0.8.2/umd/index.js';
      s.crossOrigin = 'anonymous';
      s.onload = function () { resolve(window.fflate); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return _ready;
  }

  /* ---------- helpers ---------- */

  function safeStem(file) {
    return (file.name || 'archive').replace(/\.[^.]+$/, '').replace(/[^\w\-]/g, '_').slice(0, 64);
  }

  async function readFileAsU8(file) {
    var buf = await FileLabs.readFileAsArrayBuffer(file);
    return new Uint8Array(buf);
  }

  /* ---------- batch compress (ZIP) ---------- */

  async function compressBatch(files) {
    var fflate = await loadFflate();
    var zipData = {};
    for (var i = 0; i < files.length; i++) {
      var u8 = await readFileAsU8(files[i]);
      var name = files[i].name || ('file_' + (i + 1));
      // Avoid duplicate names
      if (zipData[name]) {
        var base = name.replace(/\.[^.]+$/, '');
        var ext = name.includes('.') ? '.' + name.split('.').pop() : '';
        name = base + '_' + (i + 1) + ext;
      }
      zipData[name] = [u8, { level: 6 }];
    }
    var zipBytes = await new Promise(function (resolve, reject) {
      fflate.zip(zipData, function (err, data) {
        if (err) reject(err);
        else resolve(data);
      });
    });
    var blob = new Blob([zipBytes], { type: 'application/zip' });
    return FileLabs.buildMultiResult(blob, 'compressed_batch.zip');
  }

  /* ---------- single file compress (ZIP wrapper) ---------- */

  async function compressFile(file, format) {
    var fflate = await loadFflate();
    format = (format || 'zip').toLowerCase();
    var u8 = await readFileAsU8(file);
    var stem = safeStem(file);
    var origName = file.name || 'file';

    if (format === 'gz' || format === 'gzip') {
      var gz = await new Promise(function (resolve, reject) {
        fflate.gzip(u8, { level: 9 }, function (err, data) {
          if (err) reject(err); else resolve(data);
        });
      });
      var blob = new Blob([gz], { type: 'application/gzip' });
      return FileLabs.buildLocalResult(file, blob, origName + '.gz');
    }

    // Default: ZIP
    var zipData = {};
    zipData[origName] = [u8, { level: 6 }];
    var zipBytes = await new Promise(function (resolve, reject) {
      fflate.zip(zipData, function (err, data) {
        if (err) reject(err); else resolve(data);
      });
    });
    var zipBlob = new Blob([zipBytes], { type: 'application/zip' });
    return FileLabs.buildLocalResult(file, zipBlob, stem + '.zip');
  }

  /* ---------- export ---------- */

  window.ArchiveProcessor = {
    compressBatch: compressBatch,
    compressFile: compressFile
  };
})();

/* =========================================================
   FileLabs — pdf-processor.js
   Traitement PDF 100% côté client via pdf-lib (CDN).
   Opérations supportées : merge, split, rotate, delete-pages,
   page-numbers, watermark, protect, compress, to-jpg, from-jpg.
   ========================================================= */
(function () {
  'use strict';

  /* ---- loader CDN pdf-lib ---- */
  var _pdfLibReady = null;

  function loadPdfLib() {
    if (_pdfLibReady) return _pdfLibReady;
    _pdfLibReady = new Promise(function (resolve, reject) {
      if (window.PDFLib) { resolve(window.PDFLib); return; }
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/pdf-lib@1.17.1/dist/pdf-lib.min.js';
      s.crossOrigin = 'anonymous';
      s.onload = function () { resolve(window.PDFLib); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return _pdfLibReady;
  }

  /* ---- loader CDN pdfjs (pour to-jpg) ---- */
  var _pdfjsReady = null;

  function loadPdfjs() {
    if (_pdfjsReady) return _pdfjsReady;
    _pdfjsReady = new Promise(function (resolve, reject) {
      if (window.pdfjsLib) { resolve(window.pdfjsLib); return; }
      var s = document.createElement('script');
      // On préfère la version déjà présente dans le projet (/pdf.js/)
      s.src = '/pdf.js/build/pdf.mjs';
      s.type = 'module';
      s.onload = function () {
        if (window.pdfjsLib) { resolve(window.pdfjsLib); return; }
        // fallback CDN
        var s2 = document.createElement('script');
        s2.src = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.min.mjs';
        s2.type = 'module';
        s2.onload = function () { resolve(window.pdfjsLib); };
        s2.onerror = reject;
        document.head.appendChild(s2);
      };
      s.onerror = function () {
        var s3 = document.createElement('script');
        s3.src = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.min.mjs';
        s3.type = 'module';
        s3.onload = function () { resolve(window.pdfjsLib); };
        s3.onerror = reject;
        document.head.appendChild(s3);
      };
      document.head.appendChild(s);
    });
    return _pdfjsReady;
  }

  /* ---------- helpers ---------- */

  function stemName(file) {
    return (file.name || 'document').replace(/\.[^.]+$/, '');
  }

  function parsePageRanges(spec, totalPages) {
    // "1,3-5,7" → [1,3,4,5,7] (1-indexed)
    var pages = new Set();
    var parts = (spec || '').split(',');
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i].trim();
      if (!p) continue;
      var dash = p.indexOf('-');
      if (dash > 0) {
        var a = parseInt(p.slice(0, dash));
        var b = parseInt(p.slice(dash + 1));
        for (var j = a; j <= b && j <= totalPages; j++) {
          if (j >= 1) pages.add(j);
        }
      } else {
        var n = parseInt(p);
        if (n >= 1 && n <= totalPages) pages.add(n);
      }
    }
    return Array.from(pages).sort(function (a, b) { return a - b; });
  }

  async function readAsArrayBuffer(file) {
    return FileLabs.readFileAsArrayBuffer(file);
  }

  async function pdfToBytes(pdfDoc) {
    return pdfDoc.save();
  }

  function bytesToBlob(bytes) {
    return new Blob([bytes], { type: 'application/pdf' });
  }

  /* ---------- merge ---------- */

  async function merge(files) {
    var PDFLib = await loadPdfLib();
    var merged = await PDFLib.PDFDocument.create();
    for (var i = 0; i < files.length; i++) {
      var buf = await readAsArrayBuffer(files[i]);
      var src = await PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
      var pages = await merged.copyPages(src, src.getPageIndices());
      pages.forEach(function (p) { merged.addPage(p); });
    }
    var bytes = await pdfToBytes(merged);
    var blob = bytesToBlob(bytes);
    return FileLabs.buildMultiResult(blob, 'merged.pdf');
  }

  /* ---------- split ---------- */

  async function split(file, ranges) {
    var PDFLib = await loadPdfLib();
    var buf = await readAsArrayBuffer(file);
    var src = await PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
    var total = src.getPageCount();

    // Parse ranges, e.g. "1-3,5,7-9"
    var pageList = parsePageRanges(ranges || '1-' + total, total);
    if (pageList.length === 0) throw new Error('Aucune page sélectionnée');

    // If single contiguous range or all pages → return one PDF
    var newDoc = await PDFLib.PDFDocument.create();
    var copied = await newDoc.copyPages(src, pageList.map(function (p) { return p - 1; }));
    copied.forEach(function (p) { newDoc.addPage(p); });
    var bytes = await pdfToBytes(newDoc);
    var blob = bytesToBlob(bytes);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_pages_' + pageList[0] + '-' + pageList[pageList.length - 1] + '.pdf');
  }

  /* ---------- rotate ---------- */

  async function rotate(file, rotationMap) {
    // rotationMap: { "1": 90, "3": 180, "all": 90 }
    var PDFLib = await loadPdfLib();
    var buf = await readAsArrayBuffer(file);
    var doc = await PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
    var pages = doc.getPages();
    var map = rotationMap || {};
    var allDeg = parseInt(map['all']) || 0;
    for (var i = 0; i < pages.length; i++) {
      var deg = parseInt(map[String(i + 1)]) || allDeg;
      if (deg) {
        var cur = pages[i].getRotation().angle;
        pages[i].setRotation(PDFLib.degrees((cur + deg) % 360));
      }
    }
    var bytes = await pdfToBytes(doc);
    var blob = bytesToBlob(bytes);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_rotated.pdf');
  }

  /* ---------- delete pages ---------- */

  async function deletePages(file, pages) {
    // pages: array of 1-indexed page numbers to DELETE
    var PDFLib = await loadPdfLib();
    var buf = await readAsArrayBuffer(file);
    var src = await PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
    var total = src.getPageCount();
    var toDelete = new Set(pages.map(Number));
    var keep = [];
    for (var i = 1; i <= total; i++) {
      if (!toDelete.has(i)) keep.push(i - 1);
    }
    var newDoc = await PDFLib.PDFDocument.create();
    var copied = await newDoc.copyPages(src, keep);
    copied.forEach(function (p) { newDoc.addPage(p); });
    var bytes = await pdfToBytes(newDoc);
    var blob = bytesToBlob(bytes);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_deleted.pdf');
  }

  /* ---------- watermark (texte) ---------- */

  async function watermark(file, text, options) {
    var PDFLib = await loadPdfLib();
    options = options || {};
    var opacity = parseFloat(options.opacity) || 0.3;
    var color = options.color || '#ff0000';
    var size = parseInt(options.size) || 48;
    var angle = parseInt(options.angle) || 45;

    // Parse hex color → r,g,b 0-1
    var r = parseInt(color.slice(1, 3), 16) / 255;
    var g = parseInt(color.slice(3, 5), 16) / 255;
    var b = parseInt(color.slice(5, 7), 16) / 255;

    var buf = await readAsArrayBuffer(file);
    var doc = await PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
    var font = await doc.embedFont(PDFLib.StandardFonts.HelveticaBold);
    var pages = doc.getPages();
    var rad = (angle * Math.PI) / 180;

    for (var i = 0; i < pages.length; i++) {
      var page = pages[i];
      var w = page.getWidth();
      var h = page.getHeight();
      page.drawText(text, {
        x: w / 2 - (font.widthOfTextAtSize(text, size) / 2) * Math.cos(rad),
        y: h / 2 - size / 2,
        size: size,
        font: font,
        color: PDFLib.rgb(r, g, b),
        opacity: opacity,
        rotate: PDFLib.degrees(angle)
      });
    }
    var bytes = await pdfToBytes(doc);
    var blob = bytesToBlob(bytes);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_watermarked.pdf');
  }

  /* ---------- page numbers ---------- */

  async function pageNumbers(file, options) {
    var PDFLib = await loadPdfLib();
    options = options || {};
    var position = options.position || 'bottom-center'; // top/bottom + left/center/right
    var size = parseInt(options.size) || 12;
    var margin = parseInt(options.margin) || 20;

    var buf = await readAsArrayBuffer(file);
    var doc = await PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
    var font = await doc.embedFont(PDFLib.StandardFonts.Helvetica);
    var pages = doc.getPages();

    for (var i = 0; i < pages.length; i++) {
      var page = pages[i];
      var w = page.getWidth();
      var h = page.getHeight();
      var label = String(i + 1);
      var tw = font.widthOfTextAtSize(label, size);

      var x, y;
      var posLower = position.toLowerCase();
      // x
      if (posLower.includes('left')) x = margin;
      else if (posLower.includes('right')) x = w - tw - margin;
      else x = (w - tw) / 2;
      // y
      if (posLower.includes('top')) y = h - margin - size;
      else y = margin;

      page.drawText(label, {
        x: x, y: y,
        size: size,
        font: font,
        color: PDFLib.rgb(0, 0, 0)
      });
    }
    var bytes = await pdfToBytes(doc);
    var blob = bytesToBlob(bytes);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_numbered.pdf');
  }

  /* ---------- protect (basique — note: pdf-lib ne chiffre pas nativement) ---------- */
  // pdf-lib ne supporte pas encore le chiffrement AES-256.
  // On retourne le PDF avec une note dans les métadonnées.
  // Le vrai chiffrement est fait côté serveur en mode local.
  async function protect(file, _password) {
    throw new Error('La protection par mot de passe requiert le mode local (app). En mode web, utilisez l\'application téléchargeable.');
  }

  /* ---------- unlock ---------- */

  async function unlock(file) {
    var PDFLib = await loadPdfLib();
    var buf = await readAsArrayBuffer(file);
    // Tenter sans mot de passe (PDFs avec protection vide)
    var doc = await PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
    var bytes = await pdfToBytes(doc);
    var blob = bytesToBlob(bytes);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_unlocked.pdf');
  }

  /* ---------- compress (re-save, léger gain) ---------- */

  async function compress(file, _quality) {
    var PDFLib = await loadPdfLib();
    var buf = await readAsArrayBuffer(file);
    var doc = await PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
    var bytes = await doc.save({ useObjectStreams: true });
    var blob = bytesToBlob(bytes);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_compressed.pdf');
  }

  /* ---------- PDF → JPG (via canvas + pdf.js) ---------- */

  async function toJpg(file, dpi) {
    dpi = parseInt(dpi) || 150;
    var scale = dpi / 72;

    // pdf.js est déjà servi localement dans le projet
    if (!window.pdfjsLib) {
      throw new Error('pdf.js non disponible. Rechargez la page.');
    }
    var buf = await readAsArrayBuffer(file);
    var pdf = await window.pdfjsLib.getDocument({ data: buf }).promise;
    var blobs = [];
    for (var i = 1; i <= pdf.numPages; i++) {
      var page = await pdf.getPage(i);
      var viewport = page.getViewport({ scale: scale });
      var canvas = document.createElement('canvas');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      var ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      await page.render({ canvasContext: ctx, viewport: viewport }).promise;
      var blob = await new Promise(function (res, rej) {
        canvas.toBlob(function (b) { b ? res(b) : rej(new Error('canvas→blob failed')); }, 'image/jpeg', 0.92);
      });
      blobs.push(blob);
    }

    if (blobs.length === 1) {
      return FileLabs.buildLocalResult(file, blobs[0], stemName(file) + '_page_1.jpg');
    }

    // Multiple pages → ZIP via fflate (lazy load)
    var fflate = await loadFflate();
    var zipData = {};
    for (var j = 0; j < blobs.length; j++) {
      var ab = await blobs[j].arrayBuffer();
      zipData['page_' + (j + 1) + '.jpg'] = new Uint8Array(ab);
    }
    var zipBytes = await new Promise(function (resolve, reject) {
      fflate.zip(zipData, function (err, data) {
        if (err) reject(err);
        else resolve(data);
      });
    });
    var zipBlob = new Blob([zipBytes], { type: 'application/zip' });
    return FileLabs.buildLocalResult(file, zipBlob, stemName(file) + '_pages.zip');
  }

  /* ---------- JPG → PDF ---------- */

  async function fromJpg(files) {
    var PDFLib = await loadPdfLib();
    var doc = await PDFLib.PDFDocument.create();
    for (var i = 0; i < files.length; i++) {
      var buf = await readAsArrayBuffer(files[i]);
      var mime = files[i].type || '';
      var img;
      if (mime === 'image/png') {
        img = await doc.embedPng(buf);
      } else {
        img = await doc.embedJpg(buf);
      }
      var page = doc.addPage([img.width, img.height]);
      page.drawImage(img, { x: 0, y: 0, width: img.width, height: img.height });
    }
    var bytes = await pdfToBytes(doc);
    var blob = bytesToBlob(bytes);
    return FileLabs.buildMultiResult(blob, 'images.pdf');
  }

  /* ---------- fflate lazy loader ---------- */
  var _fflateReady = null;
  function loadFflate() {
    if (_fflateReady) return _fflateReady;
    _fflateReady = new Promise(function (resolve, reject) {
      if (window.fflate) { resolve(window.fflate); return; }
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/fflate@0.8.2/umd/index.js';
      s.crossOrigin = 'anonymous';
      s.onload = function () { resolve(window.fflate); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return _fflateReady;
  }

  /* ---------- repair (reserialize) ---------- */

  async function repair(file) {
    var PDFLib = await loadPdfLib();
    var buf = await readAsArrayBuffer(file);
    var doc = await PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
    var bytes = await doc.save({ useObjectStreams: true });
    var blob = bytesToBlob(bytes);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_repaired.pdf');
  }

  /* ---------- extract text ---------- */

  async function extractText(file) {
    if (!window.pdfjsLib) {
      throw new Error('pdf.js non disponible. Rechargez la page.');
    }
    var buf = await readAsArrayBuffer(file);
    var pdf = await window.pdfjsLib.getDocument({ data: buf }).promise;
    var fullText = '';
    for (var i = 1; i <= pdf.numPages; i++) {
      var page = await pdf.getPage(i);
      var content = await page.getTextContent();
      var pageText = content.items.map(function (item) { return item.str; }).join(' ');
      fullText += '--- Page ' + i + ' ---\n' + pageText + '\n\n';
    }
    var blob = new Blob([fullText], { type: 'text/plain' });
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '.txt');
  }

  /* ---------- export ---------- */

  window.PDFProcessor = {
    merge: merge,
    split: split,
    rotate: rotate,
    deletePages: deletePages,
    watermark: watermark,
    pageNumbers: pageNumbers,
    protect: protect,
    unlock: unlock,
    compress: compress,
    toJpg: toJpg,
    fromJpg: fromJpg,
    repair: repair,
    extractText: extractText
  };
})();

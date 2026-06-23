/* =========================================================
   FileLabs — image-processor.js
   Traitement images 100% côté client via Canvas API + browser-image-compression.
   Utilisé en mode web (filelabs.onrender.com) uniquement.
   ========================================================= */
(function () {
  'use strict';

  /* ---------- helpers ---------- */

  function loadImage(file) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = reject;
      img.src = URL.createObjectURL(file);
    });
  }

  function canvasToBlob(canvas, mimeType, quality) {
    return new Promise(function (resolve, reject) {
      canvas.toBlob(function (blob) {
        if (blob) resolve(blob);
        else reject(new Error('Conversion canvas→blob échouée'));
      }, mimeType, quality);
    });
  }

  function mimeForFormat(fmt) {
    var map = {
      jpg: 'image/jpeg', jpeg: 'image/jpeg',
      png: 'image/png',
      webp: 'image/webp',
      gif: 'image/gif',
      bmp: 'image/bmp',
      tiff: 'image/tiff', tif: 'image/tiff'
    };
    return map[(fmt || '').toLowerCase()] || 'image/jpeg';
  }

  function extForMime(mime) {
    var map = {
      'image/jpeg': 'jpg', 'image/png': 'png',
      'image/webp': 'webp', 'image/gif': 'gif',
      'image/bmp': 'bmp', 'image/tiff': 'tiff'
    };
    return map[mime] || 'jpg';
  }

  function stemName(file) {
    return (file.name || 'image').replace(/\.[^.]+$/, '');
  }

  /* ---------- compress ---------- */

  async function compress(file, quality) {
    // quality: 1–100 → 0.01–1.0
    var q = Math.max(1, Math.min(100, parseInt(quality) || 80)) / 100;
    var img = await loadImage(file);
    var canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(img.src);

    var mime = file.type && file.type !== 'image/gif' ? file.type : 'image/jpeg';
    // GIF et TIFF ne supportent pas la compression canvas, on convertit en JPEG
    if (mime === 'image/gif' || mime === 'image/tiff') mime = 'image/jpeg';

    var blob = await canvasToBlob(canvas, mime, q);
    var ext = extForMime(mime);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_compressed.' + ext);
  }

  /* ---------- resize ---------- */

  async function resize(file, width, height, keepRatio) {
    width = parseInt(width) || 0;
    height = parseInt(height) || 0;
    var img = await loadImage(file);
    var srcW = img.naturalWidth;
    var srcH = img.naturalHeight;

    if (keepRatio) {
      if (width && !height) height = Math.round((width / srcW) * srcH);
      else if (height && !width) width = Math.round((height / srcH) * srcW);
      else if (width && height) {
        var ratio = Math.min(width / srcW, height / srcH);
        width = Math.round(srcW * ratio);
        height = Math.round(srcH * ratio);
      }
    }
    if (!width) width = srcW;
    if (!height) height = srcH;

    var canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    var ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, 0, 0, width, height);
    URL.revokeObjectURL(img.src);

    var mime = (file.type && file.type !== 'image/gif') ? file.type : 'image/jpeg';
    if (mime === 'image/gif' || mime === 'image/tiff') mime = 'image/jpeg';
    var blob = await canvasToBlob(canvas, mime, 0.92);
    var ext = extForMime(mime);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_resized.' + ext);
  }

  /* ---------- convert ---------- */

  async function convert(file, targetFormat) {
    var allowed = ['jpeg','jpg','png','webp','gif','bmp','tiff'];
    var fmt = (targetFormat || '').toLowerCase().replace('.', '');
    if (!allowed.includes(fmt)) throw new Error('Format non supporté: ' + fmt);

    var img = await loadImage(file);
    var canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    var ctx = canvas.getContext('2d');
    // Fond blanc pour formats sans transparence
    if (fmt === 'jpeg' || fmt === 'jpg' || fmt === 'bmp') {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(img.src);

    var mime = mimeForFormat(fmt);
    var blob = await canvasToBlob(canvas, mime, 0.92);
    var outFmt = fmt === 'jpeg' ? 'jpg' : fmt;
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '.' + outFmt);
  }

  /* ---------- crop ---------- */

  async function crop(file, x, y, width, height) {
    x = parseInt(x) || 0;
    y = parseInt(y) || 0;
    width = parseInt(width) || 0;
    height = parseInt(height) || 0;

    var img = await loadImage(file);
    if (!width) width = img.naturalWidth - x;
    if (!height) height = img.naturalHeight - y;

    var canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(img, x, y, width, height, 0, 0, width, height);
    URL.revokeObjectURL(img.src);

    var mime = (file.type && file.type !== 'image/gif') ? file.type : 'image/jpeg';
    if (mime === 'image/gif' || mime === 'image/tiff') mime = 'image/jpeg';
    var blob = await canvasToBlob(canvas, mime, 0.92);
    var ext = extForMime(mime);
    return FileLabs.buildLocalResult(file, blob, stemName(file) + '_cropped.' + ext);
  }

  /* ---------- rotate / flip ---------- */

  async function rotate(file, degrees, flipH, flipV) {
    degrees = parseInt(degrees) || 0;
    var rad = (degrees * Math.PI) / 180;
    var img = await loadImage(file);
    var srcW = img.naturalWidth;
    var srcH = img.naturalHeight;

    var cos = Math.abs(Math.cos(rad));
    var sin = Math.abs(Math.sin(rad));
    var destW = Math.round(srcW * cos + srcH * sin);
    var destH = Math.round(srcW * sin + srcH * cos);

    var canvas = document.createElement('canvas');
    canvas.width = destW;
    canvas.height = destH;
    var ctx = canvas.getContext('2d');

    ctx.translate(destW / 2, destH / 2);
    ctx.rotate(rad);
    if (flipH) ctx.scale(-1, 1);
    if (flipV) ctx.scale(1, -1);
    ctx.drawImage(img, -srcW / 2, -srcH / 2);
    URL.revokeObjectURL(img.src);

    var mime = (file.type && file.type !== 'image/gif') ? file.type : 'image/jpeg';
    if (mime === 'image/gif' || mime === 'image/tiff') mime = 'image/jpeg';
    var blob = await canvasToBlob(canvas, mime, 0.92);
    var ext = extForMime(mime);
    var suffix = degrees ? '_rot' + degrees : '_flip';
    return FileLabs.buildLocalResult(file, blob, stemName(file) + suffix + '.' + ext);
  }

  /* ---------- export ---------- */

  window.ImageProcessor = {
    compress: compress,
    resize: resize,
    convert: convert,
    crop: crop,
    rotate: rotate
  };
})();

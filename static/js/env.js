/* =========================================================
   FileLabs — env.js
   Détecte si on tourne en mode web (Render/online) ou local (app).
   Fournit les helpers blob pour le mode web (traitement 100% client-side).
   ========================================================= */
(function () {
  'use strict';

  var h = location.hostname;
  var isLocal =
    h === '' ||
    h === 'localhost' ||
    h === '127.0.0.1' ||
    h === '::1' ||
    h.startsWith('192.168.') ||
    h.startsWith('10.') ||
    h.startsWith('172.16.') ||
    h.startsWith('172.17.') ||
    h.startsWith('172.18.') ||
    h.startsWith('172.19.') ||
    h.startsWith('172.2') ||
    h.startsWith('172.30.') ||
    h.startsWith('172.31.');

  /**
   * Déclenche le téléchargement d'un Blob côté client.
   * @param {string|Blob} blobOrUrl - Blob object ou blobUrl string
   * @param {string} filename
   */
  function triggerBlobDownload(blobOrUrl, filename) {
    var url = typeof blobOrUrl === 'string' ? blobOrUrl : URL.createObjectURL(blobOrUrl);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename || 'output';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    if (typeof blobOrUrl !== 'string') {
      setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
    }
  }

  /**
   * Construit un résultat "download_id" compatible avec showResult()
   * à partir d'un Blob, en mode web.
   * @param {File} originalFile
   * @param {Blob} resultBlob
   * @param {string} outputFilename
   * @returns {{ download_id: string, output_filename: string, original_size: number, output_size: number, blobUrl: string }}
   */
  function buildLocalResult(originalFile, resultBlob, outputFilename) {
    var blobUrl = URL.createObjectURL(resultBlob);
    return {
      download_id: '__blob__',
      output_filename: outputFilename,
      original_size: originalFile ? originalFile.size : 0,
      output_size: resultBlob.size,
      blobUrl: blobUrl
    };
  }

  /**
   * Construit un résultat pour les outils multi-fichiers (ex: batch, merge).
   * @param {Blob} resultBlob
   * @param {string} outputFilename
   * @returns {{ download_id: string, output_filename: string, output_size: number, blobUrl: string }}
   */
  function buildMultiResult(resultBlob, outputFilename) {
    var blobUrl = URL.createObjectURL(resultBlob);
    return {
      download_id: '__blob__',
      output_filename: outputFilename,
      original_size: 0,
      output_size: resultBlob.size,
      blobUrl: blobUrl
    };
  }

  /**
   * Lit un File en ArrayBuffer (Promise).
   * @param {File} file
   * @returns {Promise<ArrayBuffer>}
   */
  function readFileAsArrayBuffer(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function (e) { resolve(e.target.result); };
      reader.onerror = reject;
      reader.readAsArrayBuffer(file);
    });
  }

  /**
   * Lit un File en DataURL (Promise).
   * @param {File} file
   * @returns {Promise<string>}
   */
  function readFileAsDataURL(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function (e) { resolve(e.target.result); };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  /**
   * Formatte une taille en octets → chaîne lisible.
   * @param {number} bytes
   * @returns {string}
   */
  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' o';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' Ko';
    return (bytes / (1024 * 1024)).toFixed(2) + ' Mo';
  }

  window.FileLabs = {
    isWebMode: !isLocal,
    triggerBlobDownload: triggerBlobDownload,
    buildLocalResult: buildLocalResult,
    buildMultiResult: buildMultiResult,
    readFileAsArrayBuffer: readFileAsArrayBuffer,
    readFileAsDataURL: readFileAsDataURL,
    formatSize: formatSize
  };
})();

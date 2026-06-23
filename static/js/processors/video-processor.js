/* =========================================================
   FileLabs — video-processor.js
   Compression vidéo côté client via @ffmpeg/ffmpeg (WASM).
   Nécessite SharedArrayBuffer - les pages vidéo reçoivent COOP/COEP.
   Aucun shell command : traitement entièrement dans le navigateur (WASM).
   ========================================================= */
(function () {
  'use strict';

  var _ffmpegInstance = null;
  var _loading = false;
  var _loadCallbacks = [];

  /* ---- loader ffmpeg.wasm (ESM via CDN) ---- */
  function loadFFmpeg() {
    return new Promise(function (resolve, reject) {
      if (_ffmpegInstance) { resolve(_ffmpegInstance); return; }
      if (_loading) { _loadCallbacks.push({ resolve: resolve, reject: reject }); return; }
      _loading = true;

      // Vérifier SharedArrayBuffer (requis par ffmpeg.wasm multi-thread)
      if (typeof SharedArrayBuffer === 'undefined') {
        var err = new Error('SharedArrayBuffer non disponible. La compression vidéo nécessite l\'application locale.');
        _loading = false;
        reject(err);
        return;
      }

      // Import dynamique ESM
      Promise.all([
        import('https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.6/dist/esm/index.js'),
        import('https://cdn.jsdelivr.net/npm/@ffmpeg/util@0.12.1/dist/esm/index.js')
      ])
        .then(function (mods) {
          var FFmpeg = mods[0].FFmpeg;
          var fetchFile = mods[1].fetchFile;
          var toBlobURL = mods[1].toBlobURL;

          var ffmpeg = new FFmpeg();
          var baseURL = 'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/esm';

          return toBlobURL(baseURL + '/ffmpeg-core.js', 'text/javascript')
            .then(function (coreURL) {
              return toBlobURL(baseURL + '/ffmpeg-core.wasm', 'application/wasm')
                .then(function (wasmURL) {
                  return toBlobURL(baseURL + '/ffmpeg-core.worker.js', 'text/javascript')
                    .then(function (workerURL) {
                      return ffmpeg.load({ coreURL: coreURL, wasmURL: wasmURL, workerURL: workerURL });
                    })
                    .catch(function () {
                      // fallback single-thread (no worker)
                      return ffmpeg.load({ coreURL: coreURL, wasmURL: wasmURL });
                    });
                });
            })
            .then(function () {
              _ffmpegInstance = { ffmpeg: ffmpeg, fetchFile: fetchFile };
              _loading = false;
              resolve(_ffmpegInstance);
              _loadCallbacks.forEach(function (cb) { cb.resolve(_ffmpegInstance); });
              _loadCallbacks = [];
            });
        })
        .catch(function (err) {
          _loading = false;
          reject(err);
          _loadCallbacks.forEach(function (cb) { cb.reject(err); });
          _loadCallbacks = [];
        });
    });
  }

  /* ---------- compress ---------- */

  function compress(file, options, onProgress) {
    options = options || {};
    var codec = options.codec || 'libx264';
    var crf = String(parseInt(options.crf) || 28);
    var preset = options.preset || 'medium';
    var ext = 'mp4';

    return loadFFmpeg().then(function (instance) {
      var ffmpeg = instance.ffmpeg;
      var fetchFile = instance.fetchFile;

      if (onProgress) {
        ffmpeg.on('progress', function (e) { onProgress(Math.round(e.progress * 100)); });
      }

      var ts = Date.now();
      var inputExt = (file.name.split('.').pop() || 'mp4').replace(/[^a-z0-9]/gi, '');
      var inputName = 'in_' + ts + '.' + inputExt;
      var outputName = 'out_' + ts + '.' + ext;

      return fetchFile(file)
        .then(function (data) { return ffmpeg.writeFile(inputName, data); })
        .then(function () {
          return ffmpeg.exec([
            '-i', inputName,
            '-c:v', codec,
            '-crf', crf,
            '-preset', preset,
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            outputName
          ]);
        })
        .then(function () { return ffmpeg.readFile(outputName); })
        .then(function (data) {
          ffmpeg.deleteFile(inputName).catch(function () {});
          ffmpeg.deleteFile(outputName).catch(function () {});
          var blob = new Blob([data.buffer], { type: 'video/mp4' });
          var stem = file.name.replace(/\.[^.]+$/, '');
          return FileLabs.buildLocalResult(file, blob, stem + '_compressed.' + ext);
        });
    });
  }

  /* ---------- trim ---------- */

  function trim(file, startTime, endTime, onProgress) {
    return loadFFmpeg().then(function (instance) {
      var ffmpeg = instance.ffmpeg;
      var fetchFile = instance.fetchFile;

      if (onProgress) {
        ffmpeg.on('progress', function (e) { onProgress(Math.round(e.progress * 100)); });
      }

      var ts = Date.now();
      var inExt = (file.name.split('.').pop() || 'mp4').replace(/[^a-z0-9]/gi, '');
      var inputName = 'in_' + ts + '.' + inExt;
      var outputName = 'out_' + ts + '.' + inExt;

      return fetchFile(file)
        .then(function (data) { return ffmpeg.writeFile(inputName, data); })
        .then(function () {
          var args = ['-i', inputName];
          if (startTime) args.push('-ss', String(startTime));
          if (endTime) args.push('-to', String(endTime));
          args.push('-c', 'copy', outputName);
          return ffmpeg.exec(args);
        })
        .then(function () { return ffmpeg.readFile(outputName); })
        .then(function (data) {
          ffmpeg.deleteFile(inputName).catch(function () {});
          ffmpeg.deleteFile(outputName).catch(function () {});
          var stem = file.name.replace(/\.[^.]+$/, '');
          var blob = new Blob([data.buffer], { type: 'video/' + inExt });
          return FileLabs.buildLocalResult(file, blob, stem + '_trimmed.' + inExt);
        });
    });
  }

  /* ---------- is supported ---------- */

  function isSupported() {
    return typeof SharedArrayBuffer !== 'undefined' && typeof WebAssembly !== 'undefined';
  }

  /* ---------- export ---------- */

  window.VideoProcessor = {
    compress: compress,
    trim: trim,
    isSupported: isSupported,
    load: loadFFmpeg
  };
})();

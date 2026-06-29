"""
Compression d'archives et fichiers génériques
Algorithmes : zstd (vitesse), lzma/xz (ratio), gzip, brotli
Pour les archives existantes (ZIP, 7Z, RAR...) : ré-archivage avec meilleure compression
"""

from pathlib import Path
import zipfile
import tarfile
import os
import shutil
import tempfile

# Essai des imports optionnels
try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False

import lzma
import gzip

# Profils : algo par défaut + niveau
ALGO_PROFILES = {
    "light":      {"algo": "zstd", "level": 3},
    "standard":   {"algo": "zstd", "level": 9},
    "aggressive": {"algo": "lzma", "level": 9},
}

# Extensions d'archives décompressables
ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".bz2", ".tgz", ".tar.gz", ".tar.bz2"}


def compress_archive(
    input_path: Path,
    output_path: Path,
    level: str = "standard",
    algo: str = None,
    algo_level: int = None,
) -> Path:
    profile = ALGO_PROFILES.get(level, ALGO_PROFILES["standard"])
    target_algo = algo or profile["algo"]
    target_level = algo_level if algo_level is not None else profile["level"]

    ext = input_path.suffix.lower()
    is_zip = ext == ".zip"
    is_tar = ext in {".tar", ".tgz"} or input_path.name.endswith(".tar.gz") or input_path.name.endswith(".tar.bz2")

    # Si c'est une archive déjà compressée → ré-archiver les contenus
    if is_zip:
        return _recompress_zip(input_path, output_path, target_algo, target_level)
    elif is_tar:
        return _recompress_tar(input_path, output_path, target_algo, target_level)
    else:
        # Fichier brut → compresser directement
        return _compress_raw(input_path, output_path, target_algo, target_level)


def _compress_raw(input_path: Path, output_path: Path, algo: str, level: int) -> Path:
    if algo == "zstd" and HAS_ZSTD:
        out = output_path.with_suffix(".zst")
        cctx = zstd.ZstdCompressor(level=min(level, 22))
        with open(input_path, "rb") as fin, open(out, "wb") as fout:
            cctx.copy_stream(fin, fout)
        return out

    if algo == "brotli" and HAS_BROTLI:
        out = output_path.with_suffix(".br")
        data = input_path.read_bytes()
        out.write_bytes(brotli.compress(data, quality=min(level, 11)))
        return out

    if algo == "lzma":
        out = output_path.with_suffix(".xz")
        preset = min(level, 9)
        with open(input_path, "rb") as fin, lzma.open(out, "wb", preset=preset) as fout:
            shutil.copyfileobj(fin, fout)
        return out

    # Fallback : gzip
    out = output_path.with_suffix(".gz")
    with open(input_path, "rb") as fin, gzip.open(out, "wb", compresslevel=min(level, 9)) as fout:
        shutil.copyfileobj(fin, fout)
    return out


_MAX_UNCOMPRESSED = 1 * 1024 * 1024 * 1024  # 1 GB
_MAX_RATIO = 100  # zip bomb threshold


def _recompress_zip(input_path: Path, output_path: Path, algo: str, level: int) -> Path:
    """Extrait le ZIP et le ré-archive avec meilleure compression."""
    out = output_path.with_suffix(".zip")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Extraire — vérifications anti zip bomb + path traversal
        with zipfile.ZipFile(input_path, "r") as zin:
            total_uncompressed = 0
            for info in zin.infolist():
                # Path traversal
                if info.filename.startswith("/") or ".." in info.filename:
                    raise ValueError(f"Chemin suspect dans l'archive : {info.filename}")
                # Taille totale
                total_uncompressed += info.file_size
                if total_uncompressed > _MAX_UNCOMPRESSED:
                    raise ValueError("Archive trop volumineuse après décompression (limite 1 Go)")
                # Ratio (zip bomb)
                if info.compress_size > 0 and info.file_size / info.compress_size > _MAX_RATIO:
                    raise ValueError("Ratio de compression suspect (possible zip bomb)")
            zin.extractall(tmpdir)

        # Ré-archiver avec compression maximale
        compress_type = zipfile.ZIP_DEFLATED
        compress_level = min(level, 9)

        with zipfile.ZipFile(out, "w", compression=compress_type, compresslevel=compress_level) as zout:
            tmppath = Path(tmpdir)
            for file in tmppath.rglob("*"):
                if file.is_file():
                    zout.write(file, file.relative_to(tmppath))

    return out


def _recompress_tar(input_path: Path, output_path: Path, algo: str, level: int) -> Path:
    """Extrait le TAR et le ré-archive en .tar.gz avec meilleure compression."""
    out = output_path.with_suffix("").with_suffix(".tar.gz")

    # Détecter le mode d'ouverture
    name = input_path.name.lower()
    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        mode_r = "r:gz"
    elif name.endswith(".tar.bz2"):
        mode_r = "r:bz2"
    else:
        mode_r = "r:*"

    with tempfile.TemporaryDirectory() as tmpdir:
        with tarfile.open(input_path, mode_r) as tin:
            total_uncompressed = 0
            for member in tin.getmembers():
                # Path traversal
                if member.name.startswith("/") or ".." in member.name:
                    raise ValueError(f"Chemin suspect dans l'archive : {member.name}")
                # Taille totale
                total_uncompressed += member.size
                if total_uncompressed > _MAX_UNCOMPRESSED:
                    raise ValueError("Archive trop volumineuse après décompression (limite 1 Go)")
            tin.extractall(tmpdir)

        with tarfile.open(out, "w:gz", compresslevel=min(level, 9)) as tout:
            tmppath = Path(tmpdir)
            for file in tmppath.rglob("*"):
                if file.is_file():
                    tout.add(file, arcname=file.relative_to(tmppath))

    return out

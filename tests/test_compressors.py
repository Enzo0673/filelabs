"""
Tests unitaires FileLab
Run : py -m pytest tests/ -v
"""
import io
import zipfile
import tempfile
import pytest
from pathlib import Path

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_pdf(n_pages=2) -> bytes:
    """Crée un PDF minimal valide avec n pages (texte simple)."""
    import pikepdf
    pdf = pikepdf.Pdf.new()
    for _ in range(n_pages):
        page = pikepdf.Page(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Page,
                MediaBox=pikepdf.Array([0, 0, 612, 792]),
            )
        )
        pdf.pages.append(page)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


# ─── _parse_ranges ─────────────────────────────────────────────────────────────

from compressors.pdf.tools import _parse_ranges

def test_parse_ranges_single():
    assert _parse_ranges("1", 5) == [[0]]

def test_parse_ranges_range():
    assert _parse_ranges("1-3", 5) == [[0, 1, 2]]

def test_parse_ranges_mixed():
    assert _parse_ranges("1,3-4", 5) == [[0], [2, 3]]

def test_parse_ranges_out_of_bounds():
    with pytest.raises(ValueError):
        _parse_ranges("6", 5)

def test_parse_ranges_invalid_range():
    with pytest.raises(ValueError):
        _parse_ranges("3-1", 5)

def test_parse_ranges_bad_format():
    with pytest.raises(ValueError):
        _parse_ranges("abc", 5)


# ─── watermark_pdf (échappement) ───────────────────────────────────────────────

from compressors.pdf.tools import watermark_pdf

def test_watermark_special_chars():
    """Les parenthèses et backslashes ne doivent pas crasher."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        out = Path(d) / "out.pdf"
        inp.write_bytes(_make_pdf(1))
        # Ne doit pas lever d'exception
        watermark_pdf(inp, out, text="Test (parenthèses) et \\backslash")
        assert out.exists() and out.stat().st_size > 0

def test_watermark_long_text_truncated():
    """Texte > 200 chars doit être tronqué sans erreur."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        out = Path(d) / "out.pdf"
        inp.write_bytes(_make_pdf(1))
        long_text = "A" * 300
        watermark_pdf(inp, out, text=long_text)
        assert out.exists()


# ─── rotate_pdf_map (validation angles) ───────────────────────────────────────

from compressors.pdf.tools import rotate_pdf_map

def test_rotate_valid_angle():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        out = Path(d) / "out.pdf"
        inp.write_bytes(_make_pdf(2))
        rotate_pdf_map(inp, out, rotation_map="1:90")
        assert out.exists()

def test_rotate_invalid_angle():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        out = Path(d) / "out.pdf"
        inp.write_bytes(_make_pdf(2))
        with pytest.raises(ValueError, match="Angle invalide"):
            rotate_pdf_map(inp, out, rotation_map="1:45")

def test_rotate_all_valid_angles():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        out = Path(d) / "out.pdf"
        inp.write_bytes(_make_pdf(4))
        rotate_pdf_map(inp, out, rotation_map="1:0,2:90,3:180,4:270")
        assert out.exists()


# ─── Archive zip bomb protection ──────────────────────────────────────────────

from compressors.archive import _MAX_RATIO, _MAX_UNCOMPRESSED

def test_zip_bomb_constants():
    """Vérifie que les limites de protection sont en place."""
    assert _MAX_RATIO == 100
    assert _MAX_UNCOMPRESSED == 1 * 1024 * 1024 * 1024  # 1 GB

def test_zip_path_traversal_detection():
    """Un ZIP avec path traversal doit être rejeté."""
    from compressors.archive import compress_archive
    with tempfile.TemporaryDirectory() as d:
        # Créer un ZIP avec un chemin malveillant
        malicious_zip = Path(d) / "malicious.zip"
        with zipfile.ZipFile(malicious_zip, "w") as zf:
            zf.writestr("../../../etc/passwd", "root:x:0:0")
        out = Path(d) / "out.zip"
        with pytest.raises((ValueError, Exception)):
            compress_archive(malicious_zip, out)


# ─── extract_pdf_text ─────────────────────────────────────────────────────────

from compressors.pdf.tools import extract_pdf_text

def test_extract_text_empty_pdf():
    """Un PDF sans texte doit être détecté comme scanné."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        inp.write_bytes(_make_pdf(2))
        result = extract_pdf_text(str(inp))
        assert result["page_count"] == 2
        assert result["is_scanned"] is True  # pages vides = pas de texte

def test_extract_text_structure():
    """La structure de retour doit avoir les bonnes clés."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        inp.write_bytes(_make_pdf(3))
        result = extract_pdf_text(str(inp))
        assert "pages" in result
        assert "page_count" in result
        assert "total_chars" in result
        assert "is_scanned" in result
        assert len(result["pages"]) == 3


# ─── SSRF — _validate_url dans download_images ──────────────────────────────

from compressors.image.downloader import _validate_url
from compressors.media.downloader import DownloaderError

def test_validate_url_blocks_private_ip():
    """_validate_url doit rejeter les IPs privées."""
    with pytest.raises(DownloaderError, match="non autorisée"):
        _validate_url("http://192.168.1.1/image.jpg")

def test_validate_url_blocks_loopback():
    with pytest.raises(DownloaderError, match="non autorisée"):
        _validate_url("http://127.0.0.1/image.jpg")

def test_validate_url_blocks_metadata_service():
    """Bloquer l'IP du metadata service cloud AWS."""
    with pytest.raises(DownloaderError):
        _validate_url("http://169.254.169.254/latest/meta-data/")

def test_validate_url_rejects_non_http():
    with pytest.raises(DownloaderError, match="http"):
        _validate_url("file:///etc/passwd")

def test_validate_url_rejects_ftp():
    with pytest.raises(DownloaderError, match="http"):
        _validate_url("ftp://example.com/image.jpg")

from unittest.mock import patch, MagicMock

def test_download_images_validates_img_url():
    """download_images() doit rejeter les img_url pointant vers des IPs privées.

    Sans le fix, subprocess.run serait appelé avec l'URL interne (SSRF).
    Avec le fix, _validate_url lève DownloaderError avant d'atteindre subprocess.
    On patche subprocess.run pour simuler un succès afin d'isoler la validation.
    """
    import tempfile
    from pathlib import Path
    from compressors.image.downloader import download_images

    fake_info = {
        "title": "Test",
        "images": [{"index": 0, "thumbnail": "http://192.168.1.1/img.jpg",
                     "ext": "jpg", "url": "http://192.168.1.1/img.jpg"}],
    }

    def fake_subprocess_run(cmd, **kwargs):
        # Simule un succès de yt-dlp en créant le fichier destination
        dest = None
        for i, arg in enumerate(cmd):
            if arg == "-o" and i + 1 < len(cmd):
                dest = Path(cmd[i + 1])
                break
        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"\xff\xd8\xff\xe0")  # fake JPEG header
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch("compressors.image.downloader.get_media_info", return_value=fake_info):
        with patch("compressors.image.downloader.subprocess.run", side_effect=fake_subprocess_run):
            with tempfile.TemporaryDirectory() as tmp:
                with pytest.raises(DownloaderError, match="non autorisée"):
                    download_images("https://www.instagram.com/p/abc/", [0], Path(tmp))


# ─── Rate limit — /media/ couvert ──────────────────────────────────────────

def test_processing_paths_includes_media():
    """_PROCESSING_PATHS doit inclure /media/ pour le rate limiting."""
    import main as app_module
    assert "/media/" in app_module._PROCESSING_PATHS, (
        "/media/ absent de _PROCESSING_PATHS — les routes image-downloader "
        "ne sont pas protégées par le rate limiter."
    )


# ─── Magic bytes — /video/to-text ───────────────────────────────────────────

def test_is_exec_magic_rejects_windows_pe():
    import main as app_module
    assert app_module._is_exec_magic(b'\x4d\x5a\x90\x00\x03\x00') is True  # MZ

def test_is_exec_magic_rejects_elf():
    import main as app_module
    assert app_module._is_exec_magic(b'\x7fELF\x02\x01\x01\x00') is True

def test_is_exec_magic_rejects_php():
    import main as app_module
    assert app_module._is_exec_magic(b'<?php echo "hi";') is True

def test_is_exec_magic_rejects_html():
    import main as app_module
    assert app_module._is_exec_magic(b'<html><body>') is True
    assert app_module._is_exec_magic(b'<!DOCTYPE html>') is True

def test_is_exec_magic_accepts_mp3_id3():
    import main as app_module
    assert app_module._is_exec_magic(b'ID3\x03\x00\x00\x00') is False

def test_is_exec_magic_accepts_mkv():
    import main as app_module
    assert app_module._is_exec_magic(b'\x1a\x45\xdf\xa3\x9f') is False

def test_is_exec_magic_accepts_unknown():
    """Un fichier sans signature connue doit passer (permissif)."""
    import main as app_module
    assert app_module._is_exec_magic(b'\x00\x00\x00\x20\x66\x74\x79\x70') is False  # MP4 ftyp


# ─── compress_image ──────────────────────────────────────────────────────────

import tempfile
from pathlib import Path
from PIL import Image
from compressors.image.compress import compress_image


def _make_jpg(size=(20, 20)) -> bytes:
    img = Image.new("RGB", size, color=(100, 149, 237))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png(size=(20, 20)) -> bytes:
    img = Image.new("RGBA", size, color=(100, 149, 237, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_compress_image_jpg_standard():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.jpg"
        out = Path(d) / "output.jpg"
        inp.write_bytes(_make_jpg())
        result = compress_image(inp, out, level="standard")
        assert result.exists()
        assert result.stat().st_size > 0


def test_compress_image_png_aggressive():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.png"
        out = Path(d) / "output.png"
        inp.write_bytes(_make_png())
        result = compress_image(inp, out, level="aggressive")
        assert result.exists()
        assert result.stat().st_size > 0


def test_compress_image_all_levels():
    for level in ("light", "standard", "aggressive"):
        with tempfile.TemporaryDirectory() as d:
            inp = Path(d) / "input.jpg"
            out = Path(d) / "output.jpg"
            inp.write_bytes(_make_jpg())
            result = compress_image(inp, out, level=level)
            assert result.exists(), f"Niveau {level} n'a pas produit de fichier"


def test_compress_image_missing_file_raises():
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(Exception):
            compress_image(Path(d) / "missing.jpg", Path(d) / "out.jpg")


# ─── compress_pdf ────────────────────────────────────────────────────────────

from compressors.pdf.compress import compress_pdf


def test_compress_pdf_standard():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.pdf"
        out = Path(d) / "output.pdf"
        inp.write_bytes(_make_pdf(1))
        result = compress_pdf(inp, out, level="standard")
        assert result.exists()
        assert result.stat().st_size > 0


def test_compress_pdf_all_levels():
    for level in ("light", "standard", "aggressive"):
        with tempfile.TemporaryDirectory() as d:
            inp = Path(d) / "input.pdf"
            out = Path(d) / "output.pdf"
            inp.write_bytes(_make_pdf(1))
            result = compress_pdf(inp, out, level=level)
            assert result.exists(), f"Niveau {level} n'a pas produit de fichier"


def test_compress_pdf_no_metadata():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.pdf"
        out = Path(d) / "output.pdf"
        inp.write_bytes(_make_pdf(1))
        result = compress_pdf(inp, out, remove_metadata=True)
        assert result.exists()


# ─── compress_archive ────────────────────────────────────────────────────────

from compressors.archive import compress_archive


def _make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.txt", "hello world " * 100)
    return buf.getvalue()


def test_compress_archive_zip_standard():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.zip"
        out = Path(d) / "output.zip"
        inp.write_bytes(_make_zip())
        result = compress_archive(inp, out, level="standard")
        assert result.exists()
        assert result.stat().st_size > 0


def test_compress_archive_all_levels():
    for level in ("light", "standard", "aggressive"):
        with tempfile.TemporaryDirectory() as d:
            inp = Path(d) / "input.zip"
            out = Path(d) / "output.zip"
            inp.write_bytes(_make_zip())
            result = compress_archive(inp, out, level=level)
            assert result.exists(), f"Niveau {level} n'a pas produit de fichier"


def test_compress_archive_missing_file_raises():
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(Exception):
            compress_archive(Path(d) / "missing.zip", Path(d) / "out.zip")


# ─── R1 — ThreadPoolExecutor propagation d'exceptions ────────────────────────

from unittest.mock import patch


def test_compress_pdf_propagates_thread_exception():
    """Les exceptions dans les threads de recompression doivent remonter."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.pdf"
        out = Path(d) / "output.pdf"
        inp.write_bytes(_make_pdf(1))
        with patch(
            "compressors.pdf.compress._recompress_page_images",
            side_effect=RuntimeError("thread error simulé"),
        ):
            with pytest.raises(RuntimeError, match="thread error simulé"):
                compress_pdf(inp, out)

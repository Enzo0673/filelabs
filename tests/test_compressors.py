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

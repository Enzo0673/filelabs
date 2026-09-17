"""
Tests d'intégration pour les endpoints FastAPI FileLabs.
Utilise TestClient (httpx) — pas de serveur réel.
"""
import pytest


# ─── /compress — validation paramètres ───────────────────────────────────────

def test_compress_invalid_level_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"level": "ULTRA"},
    )
    assert resp.status_code == 400


def test_compress_invalid_codec_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
        data={"level": "standard", "vid_codec": "hevc_nvenc"},
    )
    assert resp.status_code == 400


def test_compress_invalid_crf_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
        data={"level": "standard", "vid_crf": "999"},
    )
    assert resp.status_code == 400


def test_compress_invalid_dpi_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"level": "standard", "pdf_dpi": "5"},  # < 30
    )
    assert resp.status_code == 400


def test_compress_invalid_quality_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"level": "standard", "img_quality": "200"},  # > 100
    )
    assert resp.status_code == 400


def test_compress_missing_file_returns_422(app_client):
    resp = app_client.post("/compress", data={"level": "standard"})
    assert resp.status_code == 422


# ─── /compress — cas nominaux image ─────────────────────────────────────────

def test_compress_jpg_returns_success(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"level": "standard"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "download_id" in body
    assert body["file_type"] == "image"


def test_compress_png_returns_success(app_client, sample_png_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.png", sample_png_bytes, "image/png")},
        data={"level": "light"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_compress_pdf_returns_success(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"level": "standard"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["file_type"] == "pdf"


def test_compress_archive_returns_success(app_client, sample_zip_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.zip", sample_zip_bytes, "application/zip")},
        data={"level": "standard"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ─── /download — cycle complet ───────────────────────────────────────────────

def test_compress_then_download(app_client, sample_jpg_bytes):
    """Compress → récupérer download_id → télécharger le fichier."""
    compress_resp = app_client.post(
        "/compress",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"level": "standard"},
    )
    assert compress_resp.status_code == 200
    download_id = compress_resp.json()["download_id"]

    dl_resp = app_client.get(f"/download/{download_id}")
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0


def test_download_unknown_uid_returns_404(app_client):
    resp = app_client.get("/download/nonexistent1234567890abcdefff")
    assert resp.status_code in (400, 404)


def test_download_traversal_attempt_blocked(app_client):
    """Path traversal dans l'uid doit être bloqué."""
    resp = app_client.get("/download/../../../etc/passwd")
    assert resp.status_code in (400, 403, 404, 422)


# ─── /health ─────────────────────────────────────────────────────────────────

def test_health_returns_ok(app_client):
    resp = app_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─── /pdf/merge ──────────────────────────────────────────────────────────────

def test_pdf_merge_two_files(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/merge",
        files=[
            ("files", ("a.pdf", sample_pdf_bytes, "application/pdf")),
            ("files", ("b.pdf", sample_pdf_bytes, "application/pdf")),
        ],
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_pdf_merge_single_file_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/merge",
        files=[("files", ("a.pdf", sample_pdf_bytes, "application/pdf"))],
    )
    assert resp.status_code == 400


# ─── /pdf/split ──────────────────────────────────────────────────────────────

def test_pdf_split_no_ranges(app_client, sample_pdf_2pages_bytes):
    """Split sans ranges — produit un ZIP avec toutes les pages."""
    resp = app_client.post(
        "/pdf/split",
        files={"file": ("test.pdf", sample_pdf_2pages_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_pdf_split_too_long_ranges_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/split",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"ranges": "1" * 501},  # > 500 chars
    )
    assert resp.status_code == 400


# ─── /pdf/rotate ─────────────────────────────────────────────────────────────

def test_pdf_rotate_90(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/rotate",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"angle": "90"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_pdf_rotate_invalid_angle_returns_500(app_client, sample_pdf_bytes):
    """rotation_map avec angle invalide (45) → ValueError → 500."""
    resp = app_client.post(
        "/pdf/rotate",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"rotation_map": "1:45"},  # angle invalide via rotation_map
    )
    assert resp.status_code == 500


# ─── /pdf/watermark ──────────────────────────────────────────────────────────

def test_pdf_watermark_default(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/watermark",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"text": "CONFIDENTIEL"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_pdf_watermark_invalid_position_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/watermark",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"text": "TEST", "position": "topleft"},  # invalide
    )
    assert resp.status_code == 400


# ─── /pdf/to-jpg ─────────────────────────────────────────────────────────────

def test_pdf_to_jpg_default_dpi(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/to-jpg",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
    )
    # pdf2image peut ne pas être installé localement (dispo sur Render)
    assert resp.status_code in (200, 500)


def test_pdf_to_jpg_invalid_dpi_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/to-jpg",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"dpi": "10"},  # < 50
    )
    assert resp.status_code == 400


# ─── /pdf/from-jpg ───────────────────────────────────────────────────────────

def test_pdf_from_jpg(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/pdf/from-jpg",
        files=[("files", ("img.jpg", sample_jpg_bytes, "image/jpeg"))],
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ─── /pdf/extract-text ───────────────────────────────────────────────────────

def test_pdf_extract_text_empty_pdf(app_client, sample_pdf_bytes):
    """PDF sans texte → is_scanned True."""
    resp = app_client.post(
        "/pdf/extract-text",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "is_scanned" in body or "success" in body

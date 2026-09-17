"""
Tests pour les middlewares FastAPI FileLabs :
- Rate limiting (_ON_RENDER=True requis)
- Security headers
"""
import pytest


# ─── Security headers ─────────────────────────────────────────────────────────

def test_x_frame_options_present(app_client):
    resp = app_client.get("/health")
    assert resp.headers.get("x-frame-options") == "DENY"


def test_x_content_type_options_present(app_client):
    resp = app_client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_referrer_policy_present(app_client):
    resp = app_client.get("/health")
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_permissions_policy_present(app_client):
    resp = app_client.get("/health")
    assert "permissions-policy" in resp.headers


def test_security_headers_on_static(app_client):
    """Les headers de sécurité s'appliquent aussi aux réponses statiques."""
    resp = app_client.get("/static/style.css")
    if resp.status_code == 200:
        assert resp.headers.get("x-frame-options") == "DENY"


# ─── Rate limiting ────────────────────────────────────────────────────────────

def test_rate_limit_not_active_by_default(app_client, sample_jpg_bytes):
    """Sans _ON_RENDER=True, le rate limit ne s'applique pas."""
    for _ in range(5):
        resp = app_client.post(
            "/compress",
            files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
            data={"level": "standard"},
        )
    assert resp.status_code != 429


def test_rate_limit_triggers_when_on_render(app_client, sample_jpg_bytes, monkeypatch):
    """Avec _ON_RENDER=True, la 21e requête doit retourner 429."""
    import main as app_module
    monkeypatch.setattr(app_module, "_ON_RENDER", True)
    app_module._rate_buckets.clear()

    last_resp = None
    for _ in range(21):
        last_resp = app_client.post(
            "/compress",
            files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
            data={"level": "standard"},
        )

    assert last_resp.status_code == 429
    app_module._rate_buckets.clear()


def test_rate_limit_not_on_health(app_client, monkeypatch):
    """Le rate limit ne s'applique pas aux endpoints hors _PROCESSING_PATHS."""
    import main as app_module
    monkeypatch.setattr(app_module, "_ON_RENDER", True)
    app_module._rate_buckets.clear()

    for _ in range(25):
        resp = app_client.get("/health")
    assert resp.status_code == 200
    app_module._rate_buckets.clear()


def test_processing_paths_contains_media():
    """Régression : /media/ doit être dans _PROCESSING_PATHS (fix passe 3)."""
    import main as app_module
    assert "/media/" in app_module._PROCESSING_PATHS


def test_processing_paths_contains_video():
    import main as app_module
    assert "/video/" in app_module._PROCESSING_PATHS


def test_processing_paths_contains_pdf():
    import main as app_module
    assert "/pdf/" in app_module._PROCESSING_PATHS

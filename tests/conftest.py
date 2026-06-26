"""
Fixtures partagées pour tous les tests FileLabs.
"""
import io
import zipfile
import pytest
from PIL import Image
import pikepdf
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app_client():
    """TestClient FastAPI — simule des requêtes HTTP sans serveur réel."""
    from main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def sample_pdf_bytes():
    """PDF minimal valide — 1 page vide, généré en mémoire."""
    pdf = pikepdf.Pdf.new()
    page = pikepdf.Page(pikepdf.Dictionary(
        Type=pikepdf.Name.Page,
        MediaBox=pikepdf.Array([0, 0, 612, 792]),
    ))
    pdf.pages.append(page)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_pdf_2pages_bytes():
    """PDF minimal valide — 2 pages, pour les tests merge/split."""
    pdf = pikepdf.Pdf.new()
    for _ in range(2):
        page = pikepdf.Page(pikepdf.Dictionary(
            Type=pikepdf.Name.Page,
            MediaBox=pikepdf.Array([0, 0, 612, 792]),
        ))
        pdf.pages.append(page)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_jpg_bytes():
    """JPEG 20×20 RGB, généré en mémoire (pas de fichier disque)."""
    img = Image.new("RGB", (20, 20), color=(100, 149, 237))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_png_bytes():
    """PNG 20×20 RGBA, généré en mémoire."""
    img = Image.new("RGBA", (20, 20), color=(100, 149, 237, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_zip_bytes():
    """ZIP avec un fichier texte, généré en mémoire."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.txt", "hello world " * 100)
    return buf.getvalue()

"""
Tests unitaires pour compressors/downloader.py
Lance avec : pytest tests/test_downloader.py -v
"""
import pytest
from unittest.mock import patch, MagicMock
from compressors.downloader import get_video_info, DownloaderError


def _fake_info():
    """Simule la sortie JSON de yt-dlp --dump-json"""
    return {
        "title": "Test Video",
        "thumbnail": "https://example.com/thumb.jpg",
        "duration": 120,
        "formats": [
            {"format_id": "137", "ext": "mp4", "height": 1080, "vcodec": "avc1", "acodec": "none", "filesize": 50_000_000},
            {"format_id": "22",  "ext": "mp4", "height": 720,  "vcodec": "avc1", "acodec": "mp4a", "filesize": 30_000_000},
            {"format_id": "140", "ext": "m4a", "height": None, "vcodec": "none", "acodec": "mp4a", "filesize": 5_000_000},
            {"format_id": "18",  "ext": "mp4", "height": 360,  "vcodec": "avc1", "acodec": "mp4a", "filesize": 10_000_000},
        ],
    }


def test_get_video_info_returns_expected_shape():
    with patch("compressors.downloader._run_ytdlp_info", return_value=_fake_info()):
        info = get_video_info("https://www.youtube.com/watch?v=test")
    assert info["title"] == "Test Video"
    assert info["thumbnail"] == "https://example.com/thumb.jpg"
    assert info["duration"] == 120
    # Doit contenir l'option "Meilleure qualité" en premier
    assert info["formats"][0]["format_id"] == "bestvideo+bestaudio/best"
    assert info["formats"][0]["label"] == "Meilleure qualité"
    # Doit lister les résolutions vidéo disponibles
    labels = [f["label"] for f in info["formats"]]
    assert "1080p" in labels
    assert "720p" in labels
    assert "360p" in labels


def test_get_video_info_raises_on_too_long():
    long_info = _fake_info()
    long_info["duration"] = 7201  # > 2h
    with patch("compressors.downloader._run_ytdlp_info", return_value=long_info):
        with pytest.raises(DownloaderError, match="2 heures"):
            get_video_info("https://www.youtube.com/watch?v=test")


def test_get_video_info_raises_on_invalid_url():
    with patch("compressors.downloader._run_ytdlp_info", side_effect=DownloaderError("URL invalide")):
        with pytest.raises(DownloaderError):
            get_video_info("not-a-url")

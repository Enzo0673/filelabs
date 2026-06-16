"""Outils média : compression/édition vidéo, téléchargement (YT/TikTok/...), transcription."""
from compressors.media.video import (
    compress_video, trim_video, resize_video, merge_videos, add_text_video,
    FFMPEG_AVAILABLE,
)
from compressors.media.downloader import get_video_info, download_media, DownloaderError
from compressors.media.transcribe import transcribe_media, WHISPER_AVAILABLE

__all__ = [
    "compress_video", "trim_video", "resize_video", "merge_videos", "add_text_video",
    "FFMPEG_AVAILABLE",
    "get_video_info", "download_media", "DownloaderError",
    "transcribe_media", "WHISPER_AVAILABLE",
]

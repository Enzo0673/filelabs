"""
Transcription audio/vidéo via faster-whisper.
Installe avec : pip install faster-whisper
"""

from pathlib import Path
from typing import Optional

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


# Cache du modèle en mémoire pour éviter de le recharger à chaque requête
_model_cache: dict = {}


def _get_model(model_size: str) -> "WhisperModel":
    if model_size not in _model_cache:
        _model_cache[model_size] = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
        )
    return _model_cache[model_size]


def transcribe_media(
    input_path: Path,
    language: Optional[str] = None,
    model_size: str = "small",
) -> dict:
    """
    Transcrit un fichier vidéo ou audio.

    Retourne un dict avec :
      - text : texte brut complet
      - language : langue détectée
      - duration : durée en secondes
      - word_count : nombre de mots approximatif
      - segments : liste de {start, end, text}
    """
    if not WHISPER_AVAILABLE:
        raise RuntimeError(
            "faster-whisper n'est pas installé. "
            "Lancez : pip install faster-whisper"
        )

    if model_size not in ("tiny", "base", "small", "medium", "large-v2", "large-v3"):
        model_size = "small"

    lang = None if language == "auto" else language

    model = _get_model(model_size)

    segments_gen, info = model.transcribe(
        str(input_path),
        language=lang,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    segments = []
    full_text_parts = []
    for seg in segments_gen:
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text})
        full_text_parts.append(seg.text.strip())

    full_text = " ".join(full_text_parts)

    return {
        "text": full_text,
        "language": info.language,
        "duration": info.duration,
        "word_count": len(full_text.split()),
        "segments": segments,
    }

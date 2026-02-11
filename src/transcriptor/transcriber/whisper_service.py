"""Faster-whisper transcription service.

Wraps the ``faster-whisper`` library to transcribe audio files with
word-level timestamps.  Configured for Polish (``pl``) by default but
the language and model size are driven by :pydata:`transcriptor.config.settings`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from faster_whisper import WhisperModel

from transcriptor.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes returned by the service
# ---------------------------------------------------------------------------


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class TranscriptionSegment:
    """A single segment produced by Whisper."""

    text: str
    start: float
    end: float
    words: List[WordTimestamp] = field(default_factory=list)
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0


@dataclass
class TranscriptionResult:
    segments: List[TranscriptionSegment]
    language: str
    language_probability: float
    duration: float


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class WhisperService:
    """Thin wrapper around *faster-whisper* that lazily loads the model."""

    DEFAULT_BEAM_SIZE = 5

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        language: Optional[str] = None,
    ) -> None:
        self._model_size = model_size or settings.WHISPER_MODEL_SIZE
        self._device = device or settings.WHISPER_DEVICE
        self._compute_type = compute_type or settings.WHISPER_COMPUTE_TYPE
        self._language = language or settings.WHISPER_LANGUAGE
        self._model: Optional[WhisperModel] = None

    # -- lazy init ----------------------------------------------------------

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            logger.info(
                "Loading Whisper model %s (device=%s, compute=%s)",
                self._model_size,
                self._device,
                self._compute_type,
            )
            device = self._device
            if device == "auto":
                device = "cuda"  # faster-whisper defaults; falls back internally
            self._model = WhisperModel(
                self._model_size,
                device=device,
                compute_type=self._compute_type,
            )
            logger.info("Whisper model loaded successfully.")
        return self._model

    # -- public API ---------------------------------------------------------

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        language: Optional[str] = None,
        beam_size: Optional[int] = None,
    ) -> TranscriptionResult:
        """Transcribe *audio_path* and return structured results with word timestamps.

        Parameters
        ----------
        audio_path:
            Path to a WAV (or any ffmpeg-supported) file.
        language:
            Override the default language.
        beam_size:
            Override the default beam size.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self._get_model()
        lang = language or self._language
        bs = beam_size or self.DEFAULT_BEAM_SIZE

        logger.info("Transcribing %s (lang=%s, beam=%d)", audio_path.name, lang, bs)

        segments_gen, info = model.transcribe(
            str(audio_path),
            language=lang,
            beam_size=bs,
            word_timestamps=True,
            vad_filter=True,
        )

        segments: List[TranscriptionSegment] = []
        for seg in segments_gen:
            words = [
                WordTimestamp(
                    word=w.word.strip(),
                    start=w.start,
                    end=w.end,
                    probability=w.probability,
                )
                for w in (seg.words or [])
            ]
            segments.append(
                TranscriptionSegment(
                    text=seg.text.strip(),
                    start=seg.start,
                    end=seg.end,
                    words=words,
                    avg_logprob=seg.avg_logprob,
                    no_speech_prob=seg.no_speech_prob,
                )
            )

        logger.info(
            "Transcription complete: %d segments, detected lang=%s (%.2f)",
            len(segments),
            info.language,
            info.language_probability,
        )

        return TranscriptionResult(
            segments=segments,
            language=info.language,
            language_probability=info.language_probability,
            duration=info.duration,
        )

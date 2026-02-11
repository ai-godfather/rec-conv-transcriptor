"""Pyannote-audio speaker diarization service.

Identifies *who* speaks *when* in an audio file using ``pyannote.audio``
speaker-diarization pipeline.  Configured for 2 speakers (agent + customer)
by default via :pydata:`transcriptor.config.settings`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from transcriptor.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DiarizationSegment:
    """One contiguous region attributed to a single speaker."""

    speaker: str
    start: float
    end: float


@dataclass
class DiarizationResult:
    segments: List[DiarizationSegment]
    num_speakers: int


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PyannoteDiarizer:
    """Lazy wrapper around ``pyannote.audio`` speaker-diarization pipeline."""

    DEFAULT_NUM_SPEAKERS = 2

    def __init__(
        self,
        auth_token: Optional[str] = None,
        num_speakers: Optional[int] = None,
    ) -> None:
        self._auth_token = auth_token or settings.PYANNOTE_AUTH_TOKEN
        self._num_speakers = num_speakers or self.DEFAULT_NUM_SPEAKERS
        self._pipeline = None  # type: ignore[assignment]

    # -- lazy init ----------------------------------------------------------

    def _get_pipeline(self):  # noqa: ANN202
        """Load the pyannote pipeline on first use."""
        if self._pipeline is None:
            logger.info("Loading pyannote speaker-diarization pipeline …")
            try:
                from pyannote.audio import Pipeline  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "pyannote.audio is required for diarization. "
                    "Install it with: pip install pyannote.audio"
                ) from exc

            kwargs = {}
            if self._auth_token:
                kwargs["token"] = self._auth_token
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                **kwargs,
            )
            logger.info("Pyannote pipeline loaded successfully.")
        return self._pipeline

    # -- public API ---------------------------------------------------------

    def diarize(
        self,
        audio_path: str | Path,
        *,
        num_speakers: Optional[int] = None,
    ) -> DiarizationResult:
        """Run speaker diarization on *audio_path*.

        Parameters
        ----------
        audio_path:
            Path to a WAV file.
        num_speakers:
            Override the default expected number of speakers.

        Returns
        -------
        DiarizationResult
            Ordered list of speaker segments with timestamps.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        n_speakers = num_speakers or self._num_speakers
        pipeline = self._get_pipeline()

        logger.info(
            "Diarizing %s (num_speakers=%d)", audio_path.name, n_speakers
        )

        diarize_output = pipeline(
            str(audio_path),
            num_speakers=n_speakers,
        )

        # pyannote >=3.1 returns DiarizeOutput dataclass; extract the Annotation
        annotation = getattr(diarize_output, "speaker_diarization", diarize_output)

        segments: List[DiarizationSegment] = []
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            segments.append(
                DiarizationSegment(
                    speaker=speaker,
                    start=turn.start,
                    end=turn.end,
                )
            )

        # Sort by start time (should already be, but be safe)
        segments.sort(key=lambda s: s.start)

        unique_speakers = {s.speaker for s in segments}
        logger.info(
            "Diarization complete: %d segments, %d unique speakers",
            len(segments),
            len(unique_speakers),
        )

        return DiarizationResult(
            segments=segments,
            num_speakers=len(unique_speakers),
        )

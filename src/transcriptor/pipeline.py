"""Main transcription + diarization pipeline.

Orchestrates the full flow:

1. Accept a WAV file path.
2. Detect stereo vs mono.
3. **Stereo** — split channels (left = agent, right = customer) for perfect
   per-channel diarization.
4. **Mono** — run pyannote diarization to identify 2 speakers, then apply a
   heuristic to label them *agent* / *customer*.
5. Run faster-whisper transcription (with word-level timestamps).
6. Align diarization segments with transcription segments.
7. Return a structured :class:`PipelineResult`.
"""

from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydub import AudioSegment  # type: ignore[import-untyped]

from transcriptor.diarizer.pyannote_service import (
    DiarizationResult,
    DiarizationSegment,
    PyannoteDiarizer,
)
from transcriptor.transcriber.whisper_service import (
    TranscriptionResult,
    TranscriptionSegment,
    WhisperService,
)

logger = logging.getLogger(__name__)

SpeakerLabel = Literal["agent", "customer"]


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class AlignedSegment:
    """A transcription segment with an assigned speaker label."""

    speaker: SpeakerLabel
    text: str
    start: float
    end: float
    confidence: Optional[float] = None


@dataclass
class PipelineResult:
    """Final output of the transcription pipeline."""

    segments: List[AlignedSegment]
    full_text: str
    language: str
    duration: float
    num_speakers: int
    channel_mode: Literal["stereo", "mono"]
    raw_transcription: Optional[TranscriptionResult] = None
    raw_diarization: Optional[DiarizationResult] = None


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------


def _load_audio(path: Path) -> AudioSegment:
    """Load an audio file via pydub."""
    logger.debug("Loading audio file: %s", path)
    audio = AudioSegment.from_file(str(path))
    logger.info(
        "Audio loaded: channels=%d, sample_width=%d, frame_rate=%d, duration=%.2fs",
        audio.channels,
        audio.sample_width,
        audio.frame_rate,
        len(audio) / 1000.0,
    )
    return audio


def _split_stereo(audio: AudioSegment, workdir: Path) -> tuple[Path, Path]:
    """Split a stereo file into two mono WAV files.

    Returns (left_path, right_path) — left is agent, right is customer.
    """
    if audio.channels != 2:
        raise ValueError(f"Expected stereo audio (2 channels), got {audio.channels}")

    channels = audio.split_to_mono()
    left_path = workdir / "channel_left_agent.wav"
    right_path = workdir / "channel_right_customer.wav"

    channels[0].export(str(left_path), format="wav")
    channels[1].export(str(right_path), format="wav")

    logger.info("Stereo split complete: %s, %s", left_path.name, right_path.name)
    return left_path, right_path


# ---------------------------------------------------------------------------
# Alignment logic
# ---------------------------------------------------------------------------


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    """Return the duration of overlap between two time intervals."""
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _align_segments(
    transcription: TranscriptionResult,
    diarization: DiarizationResult,
    speaker_map: Dict[str, SpeakerLabel],
) -> List[AlignedSegment]:
    """Match each transcription segment to the best-overlapping diarization speaker.

    For every whisper segment we compute how much time overlaps with each
    diarization speaker and pick the one with the largest overlap.
    """
    aligned: List[AlignedSegment] = []

    for tseg in transcription.segments:
        # Accumulate overlap per speaker
        speaker_overlap: Dict[str, float] = {}
        for dseg in diarization.segments:
            ov = _overlap(tseg.start, tseg.end, dseg.start, dseg.end)
            if ov > 0:
                speaker_overlap[dseg.speaker] = (
                    speaker_overlap.get(dseg.speaker, 0.0) + ov
                )

        if speaker_overlap:
            raw_speaker = max(speaker_overlap, key=speaker_overlap.get)  # type: ignore[arg-type]
            label = speaker_map.get(raw_speaker, "customer")
        else:
            # No diarization segment overlaps — fallback
            label = "agent"
            logger.warning(
                "No diarization overlap for segment [%.2f–%.2f], defaulting to 'agent'",
                tseg.start,
                tseg.end,
            )

        aligned.append(
            AlignedSegment(
                speaker=label,
                text=tseg.text,
                start=tseg.start,
                end=tseg.end,
                confidence=_avg_word_confidence(tseg),
            )
        )

    return aligned


def _avg_word_confidence(seg: TranscriptionSegment) -> Optional[float]:
    if not seg.words:
        return None
    return sum(w.probability for w in seg.words) / len(seg.words)


# ---------------------------------------------------------------------------
# Speaker labelling heuristic (mono path only)
# ---------------------------------------------------------------------------

# Polish formal/sales phrases typical for call centre agents
_AGENT_PHRASES = [
    # Greetings & intro
    r"dzień dobry",
    r"dzwonię z",
    r"dzwonię ze",
    r"dzwonię w sprawie",
    r"nazywam się",
    r"mam na imię",
    # Sales language
    r"czy mogę zaproponować",
    r"mogę zaproponować",
    r"chciał\w*bym zaproponować",
    r"w promocyjnej cenie",
    r"w promocji",
    r"promocja",
    r"rabat",
    r"gratis",
    r"w cenie",
    r"kuracja",
    r"bestseller",
    r"opakowanie",
    r"opakowań",
    # Prices & numbers
    r"\d+\s*zł",
    r"\d+\s*złotych",
    r"kosztuje",
    r"oszczędność",
    r"za opakowanie",
    r"za pobraniem",
    r"płatność",
    r"metoda płatności",
    # Order & delivery
    r"dane dostawy",
    r"adres dostawy",
    r"numer zamówienia",
    r"potwierdzam zamówienie",
    r"w sprawie zamówienia",
    r"wysyłam",
    r"wysyłka",
    r"kurier",
    r"paczka",
    r"przesyłka",
    # Formal phrases
    r"potrzebuję potwierdzenia",
    r"muszę potwierdzić",
    r"czy wszystko się zgadza",
    r"czy wyraża pan\w* zgodę",
    r"czy wyraża pani zgodę",
    r"proszę pan\w",
    r"regulamin",
    r"reklamacja",
    r"gwarancja",
    # Closing
    r"miłego dnia",
    r"dziękuję za rozmowę",
    r"do widzenia",
    r"życzę miłego",
]

# Short customer-like responses
_CUSTOMER_SHORT_RESPONSES = [
    r"^tak[.,!]?\s*$",
    r"^nie[.,!]?\s*$",
    r"^no\s*$",
    r"^no tak\s*$",
    r"^no nie\s*$",
    r"^no dobrze",
    r"^no niech będzie",
    r"^niech będzie",
    r"^dokładnie",
    r"^dobrze",
    r"^ok\b",
    r"^okej",
    r"^trudno",
    r"^halo",
    r"^to znaczy",
    r"^mhm",
    r"^aha",
    r"^uhm",
    r"^no właśnie",
    r"^zgadza się",
    r"^jasne",
    r"^rozumiem",
    r"^a ile",
    r"^no to",
    r"^yyyy",
]


def _count_phrase_matches(text: str, patterns: list[str]) -> int:
    """Count how many patterns match in the given text."""
    text_lower = text.lower()
    return sum(1 for p in patterns if re.search(p, text_lower))


def _count_distinct_phrase_matches(text: str, patterns: list[str]) -> int:
    """Count how many *distinct* patterns match (each pattern counted at most once)."""
    text_lower = text.lower()
    return sum(1 for p in patterns if re.search(p, text_lower))


def _label_speakers_smart(
    diarization: DiarizationResult,
    transcription: TranscriptionResult,
) -> Dict[str, SpeakerLabel]:
    """Multi-signal heuristic to identify agent vs customer.

    Analyses ALL segments first, then assigns labels based on combined signals:
    1. Formal/sales phrase count per speaker (agent uses scripted language)
    2. Short customer response pattern matches
    3. Short segments by word count (< 5 words — customer-like)
    4. Total speaking time (agent speaks more)
    5. Average segment length in words (agent has longer turns)
    6. Diversity of agent phrases (bonus for matching many distinct patterns)
    7. First speaker bonus (weak tiebreaker)
    """
    if not diarization.segments:
        return {}

    # --- Gather diarization stats per speaker ---
    speaking_time: Dict[str, float] = {}
    first_appearance: Dict[str, float] = {}
    segment_count: Dict[str, int] = {}

    for seg in diarization.segments:
        dur = seg.end - seg.start
        speaking_time[seg.speaker] = speaking_time.get(seg.speaker, 0.0) + dur
        segment_count[seg.speaker] = segment_count.get(seg.speaker, 0) + 1
        if seg.speaker not in first_appearance:
            first_appearance[seg.speaker] = seg.start

    # Pick top-2 by speaking time
    top_speakers = sorted(speaking_time, key=speaking_time.get, reverse=True)[:2]  # type: ignore[arg-type]

    # --- Align transcription text to speakers (for analysis) ---
    speaker_texts: Dict[str, List[str]] = {sp: [] for sp in top_speakers}

    for tseg in transcription.segments:
        speaker_overlap: Dict[str, float] = {}
        for dseg in diarization.segments:
            ov = _overlap(tseg.start, tseg.end, dseg.start, dseg.end)
            if ov > 0:
                speaker_overlap[dseg.speaker] = (
                    speaker_overlap.get(dseg.speaker, 0.0) + ov
                )
        if speaker_overlap:
            best = max(speaker_overlap, key=speaker_overlap.get)  # type: ignore[arg-type]
            if best in speaker_texts:
                speaker_texts[best].append(tseg.text.strip())

    # --- Score each speaker ---
    scores: Dict[str, float] = {sp: 0.0 for sp in top_speakers}
    debug_info: Dict[str, Dict] = {}

    for sp in top_speakers:
        all_text = " ".join(speaker_texts[sp])
        info: Dict = {}

        # Signal 1: Formal/sales phrases (strong signal, +3 per match)
        agent_phrase_count = _count_phrase_matches(all_text, _AGENT_PHRASES)
        scores[sp] += agent_phrase_count * 3.0
        info["agent_phrases"] = agent_phrase_count

        # Signal 2: Short customer response patterns (-2 per match)
        short_responses = sum(
            1 for t in speaker_texts[sp]
            if _count_phrase_matches(t, _CUSTOMER_SHORT_RESPONSES) > 0
        )
        scores[sp] -= short_responses * 2.0
        info["customer_responses"] = short_responses

        # Signal 3: Short segments by word count (< 5 words = customer-like, -1.5 each)
        short_segments = sum(1 for t in speaker_texts[sp] if len(t.split()) < 5)
        scores[sp] -= short_segments * 1.5
        info["short_segments"] = short_segments

        # Signal 4: Total speaking time (agent speaks more, +2 if majority)
        total_time = sum(speaking_time.values())
        time_pct = speaking_time[sp] / total_time if total_time > 0 else 0
        if time_pct > 0.55:
            scores[sp] += 2.0
        info["time_pct"] = round(time_pct * 100, 1)

        # Signal 5: Average words per segment (agent has longer turns, +1 if > 8)
        avg_words = 0.0
        if speaker_texts[sp]:
            avg_words = sum(len(t.split()) for t in speaker_texts[sp]) / len(speaker_texts[sp])
            if avg_words > 8:
                scores[sp] += 1.0
        info["avg_words"] = round(avg_words, 1)

        # Signal 6: Diversity of agent phrases (+2 bonus if >= 3 distinct types)
        distinct_agent = _count_distinct_phrase_matches(all_text, _AGENT_PHRASES)
        if distinct_agent >= 3:
            scores[sp] += 2.0
        info["distinct_agent_phrases"] = distinct_agent

        # Signal 7: Speaks first (weak tiebreaker, +0.5)
        if first_appearance.get(sp, float("inf")) == min(first_appearance.values()):
            scores[sp] += 0.5

        info["total_segments"] = len(speaker_texts[sp])
        info["speaking_time"] = round(speaking_time[sp], 1)
        debug_info[sp] = info

    # --- Handle single-speaker edge case ---
    if len(top_speakers) == 1:
        sp = top_speakers[0]
        info = debug_info[sp]
        # If no agent language and mostly short responses, label as customer
        if info["agent_phrases"] == 0 and info["short_segments"] > info["total_segments"] * 0.5:
            logger.info(
                "Single speaker %s labelled as 'customer' (no agent phrases, %d/%d short segments)",
                sp, info["short_segments"], info["total_segments"],
            )
            return {sp: "customer"}
        logger.info("Single speaker %s labelled as 'agent' (score=%.1f)", sp, scores[sp])
        return {sp: "agent"}

    # --- Assign labels ---
    a, b = top_speakers
    if scores[a] >= scores[b]:
        agent, customer = a, b
    else:
        agent, customer = b, a

    logger.info(
        "Speaker labelling results:\n"
        "  %s → AGENT  (score=%.1f, time=%.1fs [%.0f%%], agent_phrases=%d [%d distinct], "
        "short_responses=%d, short_segs=%d, avg_words=%.1f, segments=%d)\n"
        "  %s → CUSTOMER (score=%.1f, time=%.1fs [%.0f%%], agent_phrases=%d [%d distinct], "
        "short_responses=%d, short_segs=%d, avg_words=%.1f, segments=%d)",
        agent, scores[agent], debug_info[agent]["speaking_time"], debug_info[agent]["time_pct"],
        debug_info[agent]["agent_phrases"], debug_info[agent]["distinct_agent_phrases"],
        debug_info[agent]["customer_responses"], debug_info[agent]["short_segments"],
        debug_info[agent]["avg_words"], debug_info[agent]["total_segments"],
        customer, scores[customer], debug_info[customer]["speaking_time"], debug_info[customer]["time_pct"],
        debug_info[customer]["agent_phrases"], debug_info[customer]["distinct_agent_phrases"],
        debug_info[customer]["customer_responses"], debug_info[customer]["short_segments"],
        debug_info[customer]["avg_words"], debug_info[customer]["total_segments"],
    )

    return {agent: "agent", customer: "customer"}


# ---------------------------------------------------------------------------
# Stereo pipeline
# ---------------------------------------------------------------------------


def _run_stereo_pipeline(
    audio: AudioSegment,
    audio_path: Path,
    whisper: WhisperService,
) -> PipelineResult:
    """Process a stereo recording by splitting channels."""
    logger.info("Stereo pipeline: splitting channels for %s", audio_path.name)

    with tempfile.TemporaryDirectory(prefix="transcriptor_") as tmpdir:
        workdir = Path(tmpdir)
        left_path, right_path = _split_stereo(audio, workdir)

        # Transcribe each channel
        logger.info("Transcribing agent channel (left) …")
        agent_result = whisper.transcribe(left_path)

        logger.info("Transcribing customer channel (right) …")
        customer_result = whisper.transcribe(right_path)

    # Build aligned segments from both channels
    segments: List[AlignedSegment] = []

    for seg in agent_result.segments:
        segments.append(
            AlignedSegment(
                speaker="agent",
                text=seg.text,
                start=seg.start,
                end=seg.end,
                confidence=_avg_word_confidence(seg),
            )
        )

    for seg in customer_result.segments:
        segments.append(
            AlignedSegment(
                speaker="customer",
                text=seg.text,
                start=seg.start,
                end=seg.end,
                confidence=_avg_word_confidence(seg),
            )
        )

    # Sort by time
    segments.sort(key=lambda s: s.start)

    full_text = _build_full_text(segments)
    duration = max(agent_result.duration, customer_result.duration)

    return PipelineResult(
        segments=segments,
        full_text=full_text,
        language=agent_result.language,
        duration=duration,
        num_speakers=2,
        channel_mode="stereo",
    )


# ---------------------------------------------------------------------------
# Mono pipeline
# ---------------------------------------------------------------------------


def _run_mono_pipeline(
    audio_path: Path,
    whisper: WhisperService,
    diarizer: PyannoteDiarizer,
) -> PipelineResult:
    """Process a mono recording: diarize → transcribe → align."""
    logger.info("Mono pipeline for %s", audio_path.name)

    # Step 1: Diarize
    logger.info("Running speaker diarization …")
    diarization = diarizer.diarize(audio_path)

    # Step 2: Transcribe
    logger.info("Running transcription …")
    transcription = whisper.transcribe(audio_path)

    # Step 3: Label speakers (using transcription text for smart heuristics)
    speaker_map = _label_speakers_smart(diarization, transcription)

    # Step 4: Align
    segments = _align_segments(transcription, diarization, speaker_map)

    full_text = _build_full_text(segments)

    return PipelineResult(
        segments=segments,
        full_text=full_text,
        language=transcription.language,
        duration=transcription.duration,
        num_speakers=diarization.num_speakers,
        channel_mode="mono",
        raw_transcription=transcription,
        raw_diarization=diarization,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_full_text(segments: List[AlignedSegment]) -> str:
    """Build a readable transcript with speaker labels."""
    lines: List[str] = []
    for seg in segments:
        label = seg.speaker.capitalize()
        lines.append(f"[{label}] {seg.text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


class TranscriptionPipeline:
    """High-level pipeline: WAV in → structured transcript out."""

    def __init__(
        self,
        whisper: Optional[WhisperService] = None,
        diarizer: Optional[PyannoteDiarizer] = None,
    ) -> None:
        self._whisper = whisper or WhisperService()
        self._diarizer = diarizer or PyannoteDiarizer()

    def process(self, audio_path: str | Path) -> PipelineResult:
        """Run the full pipeline on *audio_path*.

        Parameters
        ----------
        audio_path:
            Path to a WAV file (mono or stereo).

        Returns
        -------
        PipelineResult
            Structured output with aligned speaker segments, full text,
            and metadata.

        Raises
        ------
        FileNotFoundError
            If *audio_path* does not exist.
        ValueError
            If the file cannot be decoded.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info("Pipeline started for %s", audio_path)

        try:
            audio = _load_audio(audio_path)
        except Exception:
            logger.exception("Failed to load audio file %s", audio_path)
            raise

        if audio.channels >= 2:
            result = _run_stereo_pipeline(audio, audio_path, self._whisper)
        else:
            result = _run_mono_pipeline(audio_path, self._whisper, self._diarizer)

        logger.info(
            "Pipeline complete: %d segments, mode=%s, duration=%.2fs",
            len(result.segments),
            result.channel_mode,
            result.duration,
        )
        return result

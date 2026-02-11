"""Query interface for accessing transcription data."""

from sqlalchemy import func

from transcriptor.db.database import SessionLocal, init_db
from transcriptor.db.models import Recording, Segment, Speaker, Transcript


def get_all_recordings() -> list[dict]:
    """List all recordings with their status."""
    init_db()
    session = SessionLocal()
    try:
        recordings = session.query(Recording).order_by(Recording.id.desc()).all()
        return [
            {
                "id": r.id,
                "filename": r.filename,
                "filepath": r.filepath,
                "status": r.status,
                "duration": r.duration_seconds,
                "error_message": r.error_message,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in recordings
        ]
    finally:
        session.close()


def get_transcript(recording_id: int) -> dict | None:
    """Get full transcript with segments for a recording."""
    init_db()
    session = SessionLocal()
    try:
        recording = session.get(Recording, recording_id)
        if not recording:
            return None

        transcript = (
            session.query(Transcript)
            .filter(Transcript.recording_id == recording_id)
            .first()
        )
        if not transcript:
            return {
                "recording": {
                    "id": recording.id,
                    "filename": recording.filename,
                    "status": recording.status,
                },
                "transcript": None,
                "segments": [],
            }

        segments = (
            session.query(Segment)
            .filter(Segment.transcript_id == transcript.id)
            .order_by(Segment.start_time)
            .all()
        )

        # Build speaker_label -> role mapping
        speaker_labels = {s.speaker_label for s in segments if s.speaker_label}
        role_map = {}
        if speaker_labels:
            speakers = session.query(Speaker).filter(Speaker.label.in_(speaker_labels)).all()
            role_map = {sp.label: sp.role for sp in speakers}

        return {
            "recording": {
                "id": recording.id,
                "filename": recording.filename,
                "status": recording.status,
                "duration": recording.duration_seconds,
            },
            "transcript": {
                "id": transcript.id,
                "full_text": transcript.full_text,
                "language": transcript.language,
            },
            "segments": [
                {
                    "id": s.id,
                    "speaker": s.speaker_label,
                    "role": role_map.get(s.speaker_label),
                    "text": s.text,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                }
                for s in segments
            ],
        }
    finally:
        session.close()


def search_transcripts(query: str) -> list[dict]:
    """Full-text search across all transcripts and segments."""
    init_db()
    session = SessionLocal()
    try:
        pattern = f"%{query}%"

        # Search in full transcript text
        transcript_hits = (
            session.query(Transcript, Recording)
            .join(Recording, Transcript.recording_id == Recording.id)
            .filter(Transcript.full_text.ilike(pattern))
            .all()
        )

        # Search in individual segments
        segment_hits = (
            session.query(Segment, Transcript, Recording)
            .join(Transcript, Segment.transcript_id == Transcript.id)
            .join(Recording, Transcript.recording_id == Recording.id)
            .filter(Segment.text.ilike(pattern))
            .all()
        )

        results = []
        seen_recording_ids = set()

        for transcript, recording in transcript_hits:
            seen_recording_ids.add(recording.id)
            results.append(
                {
                    "recording_id": recording.id,
                    "filename": recording.filename,
                    "match_type": "transcript",
                    "text": transcript.full_text,
                }
            )

        for segment, transcript, recording in segment_hits:
            results.append(
                {
                    "recording_id": recording.id,
                    "filename": recording.filename,
                    "match_type": "segment",
                    "speaker": segment.speaker_label,
                    "text": segment.text,
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                }
            )

        return results
    finally:
        session.close()


def get_segments_by_speaker(recording_id: int, role: str) -> list[dict]:
    """Get segments for a recording filtered by speaker role (agent/customer).

    Joins Segment.speaker_label with Speaker.label to resolve role.
    """
    init_db()
    session = SessionLocal()
    try:
        transcript = (
            session.query(Transcript)
            .filter(Transcript.recording_id == recording_id)
            .first()
        )
        if not transcript:
            return []

        # Find speaker labels matching the requested role
        matching_speakers = (
            session.query(Speaker.label)
            .filter(Speaker.role == role)
            .all()
        )
        matching_labels = {sp.label for sp in matching_speakers}

        if not matching_labels:
            return []

        segments = (
            session.query(Segment)
            .filter(
                Segment.transcript_id == transcript.id,
                Segment.speaker_label.in_(matching_labels),
            )
            .order_by(Segment.start_time)
            .all()
        )

        return [
            {
                "id": s.id,
                "speaker": s.speaker_label,
                "role": role,
                "text": s.text,
                "start_time": s.start_time,
                "end_time": s.end_time,
            }
            for s in segments
        ]
    finally:
        session.close()


def swap_speakers(recording_id: int) -> bool:
    """Swap agent/customer labels for all segments of a recording.

    Returns True if swap was performed, False if recording/transcript not found.
    """
    init_db()
    session = SessionLocal()
    try:
        transcript = (
            session.query(Transcript)
            .filter(Transcript.recording_id == recording_id)
            .first()
        )
        if not transcript:
            return False

        segments = (
            session.query(Segment)
            .filter(Segment.transcript_id == transcript.id)
            .all()
        )

        swap_map = {"agent": "customer", "customer": "agent"}
        for seg in segments:
            seg.speaker_label = swap_map.get(seg.speaker_label, seg.speaker_label)

        # Rebuild full_text with swapped labels
        ordered = sorted(segments, key=lambda s: s.start_time or 0)
        lines = []
        for seg in ordered:
            label = seg.speaker_label.capitalize()
            lines.append(f"[{label}] {seg.text}")
        transcript.full_text = "\n".join(lines)

        session.commit()
        return True
    finally:
        session.close()


def get_stats() -> dict:
    """Get overall statistics: total recordings, avg duration, processing info."""
    init_db()
    session = SessionLocal()
    try:
        total = session.query(func.count(Recording.id)).scalar() or 0
        done = (
            session.query(func.count(Recording.id))
            .filter(Recording.status == "done")
            .scalar()
            or 0
        )
        pending = (
            session.query(func.count(Recording.id))
            .filter(Recording.status == "pending")
            .scalar()
            or 0
        )
        errors = (
            session.query(func.count(Recording.id))
            .filter(Recording.status == "error")
            .scalar()
            or 0
        )
        avg_duration = (
            session.query(func.avg(Recording.duration_seconds))
            .filter(Recording.duration_seconds.isnot(None))
            .scalar()
        )

        return {
            "total_recordings": total,
            "done": done,
            "pending": pending,
            "errors": errors,
            "avg_duration_seconds": round(avg_duration, 2) if avg_duration else None,
        }
    finally:
        session.close()

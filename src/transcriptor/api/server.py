"""FastAPI REST API for the transcription dashboard."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func

from transcriptor.config import settings
from transcriptor.db.database import SessionLocal, init_db
from transcriptor.db.models import Recording, Segment, Speaker, Transcript

logger = logging.getLogger(__name__)

app = FastAPI(title="Transcriptor API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pipeline/watcher state (managed via start/stop endpoints)
# ---------------------------------------------------------------------------

_watcher_thread: Optional[threading.Thread] = None
_watcher_observer = None
_watcher_stop_event = threading.Event()

# WebSocket clients for progress broadcasting
_ws_clients: list = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _recording_to_dict(r: Recording) -> dict:
    return {
        "id": r.id,
        "filename": r.filename,
        "filepath": r.filepath,
        "status": r.status,
        "duration": r.duration_seconds,
        "error_message": r.error_message,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "processed_at": r.processed_at.isoformat() if r.processed_at else None,
    }


# ---------------------------------------------------------------------------
# Recordings endpoints
# ---------------------------------------------------------------------------


@app.get("/api/recordings")
def list_recordings(
    status: Optional[str] = Query(None, description="Filter by status"),
    sort: str = Query("date_desc", description="Sort order: date_asc, date_desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """List all recordings with pagination and filtering."""
    init_db()
    session = SessionLocal()
    try:
        q = session.query(Recording)

        if status:
            q = q.filter(Recording.status == status)

        if sort == "date_asc":
            q = q.order_by(Recording.created_at.asc())
        else:
            q = q.order_by(Recording.created_at.desc())

        total = q.count()
        recordings = q.offset((page - 1) * per_page).limit(per_page).all()

        return {
            "recordings": [_recording_to_dict(r) for r in recordings],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        }
    finally:
        session.close()


@app.get("/api/recordings/{recording_id}")
def get_recording(recording_id: int):
    """Get a single recording with full transcript and segments."""
    init_db()
    session = SessionLocal()
    try:
        recording = session.get(Recording, recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")

        transcript = (
            session.query(Transcript)
            .filter(Transcript.recording_id == recording_id)
            .first()
        )

        segments = []
        transcript_dict = None
        if transcript:
            transcript_dict = {
                "id": transcript.id,
                "full_text": transcript.full_text,
                "language": transcript.language,
                "model_used": transcript.model_used,
            }
            segs = (
                session.query(Segment)
                .filter(Segment.transcript_id == transcript.id)
                .order_by(Segment.start_time)
                .all()
            )
            # Build speaker role map
            speaker_labels = {s.speaker_label for s in segs if s.speaker_label}
            role_map = {}
            if speaker_labels:
                speakers = session.query(Speaker).filter(Speaker.label.in_(speaker_labels)).all()
                role_map = {sp.label: sp.role for sp in speakers}

            segments = [
                {
                    "id": s.id,
                    "speaker": s.speaker_label,
                    "role": role_map.get(s.speaker_label),
                    "text": s.text,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "confidence": s.confidence,
                }
                for s in segs
            ]

        return {
            "recording": _recording_to_dict(recording),
            "transcript": transcript_dict,
            "segments": segments,
        }
    finally:
        session.close()


@app.get("/api/recordings/{recording_id}/segments")
def get_segments(recording_id: int):
    """Get segments with speaker labels and timestamps for a recording."""
    init_db()
    session = SessionLocal()
    try:
        recording = session.get(Recording, recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")

        transcript = (
            session.query(Transcript)
            .filter(Transcript.recording_id == recording_id)
            .first()
        )
        if not transcript:
            return {"segments": []}

        segs = (
            session.query(Segment)
            .filter(Segment.transcript_id == transcript.id)
            .order_by(Segment.start_time)
            .all()
        )

        speaker_labels = {s.speaker_label for s in segs if s.speaker_label}
        role_map = {}
        if speaker_labels:
            speakers = session.query(Speaker).filter(Speaker.label.in_(speaker_labels)).all()
            role_map = {sp.label: sp.role for sp in speakers}

        return {
            "segments": [
                {
                    "id": s.id,
                    "speaker": s.speaker_label,
                    "role": role_map.get(s.speaker_label),
                    "text": s.text,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "confidence": s.confidence,
                }
                for s in segs
            ]
        }
    finally:
        session.close()


@app.get("/api/recordings/{recording_id}/audio")
def get_audio(recording_id: int):
    """Serve the WAV file for browser playback."""
    init_db()
    session = SessionLocal()
    try:
        recording = session.get(Recording, recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        filepath = Path(recording.filepath)
    finally:
        session.close()

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    return FileResponse(
        path=str(filepath),
        media_type="audio/wav",
        filename=filepath.name,
    )


@app.post("/api/recordings/upload")
async def upload_recording(file: UploadFile = File(...)):
    """Upload a new WAV file, save to WATCH_DIR and create a DB entry."""
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="Only .wav files are supported")

    watch_dir = Path(settings.WATCH_DIR)
    watch_dir.mkdir(parents=True, exist_ok=True)

    dest = watch_dir / file.filename
    # Avoid overwriting - append suffix if file exists
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists():
            dest = watch_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    init_db()
    session = SessionLocal()
    try:
        recording = Recording(
            filename=dest.name,
            filepath=str(dest),
            status="pending",
        )
        session.add(recording)
        session.commit()
        result = _recording_to_dict(recording)
    finally:
        session.close()

    return {"recording": result, "message": "File uploaded successfully"}


@app.post("/api/recordings/{recording_id}/reprocess")
def reprocess_recording(recording_id: int):
    """Re-run transcription on a recording in a background thread."""
    init_db()
    session = SessionLocal()
    try:
        recording = session.get(Recording, recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")

        filepath = recording.filepath

        # Delete old transcripts/segments
        old_transcripts = (
            session.query(Transcript)
            .filter(Transcript.recording_id == recording_id)
            .all()
        )
        for t in old_transcripts:
            session.delete(t)

        recording.status = "pending"
        recording.error_message = None
        recording.processed_at = None
        session.commit()
    finally:
        session.close()

    # Process in background thread
    def _bg_process():
        from transcriptor.watcher.folder_watcher import _process_file
        _process_file(Path(filepath))

    thread = threading.Thread(target=_bg_process, daemon=True)
    thread.start()

    return {"message": "Reprocessing started", "recording_id": recording_id}


@app.delete("/api/recordings/{recording_id}")
def delete_recording(recording_id: int):
    """Delete a recording and its transcripts."""
    init_db()
    session = SessionLocal()
    try:
        recording = session.get(Recording, recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")

        session.delete(recording)
        session.commit()
        return {"message": "Recording deleted", "recording_id": recording_id}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@app.get("/api/search")
def search_transcripts(q: str = Query(..., min_length=1, description="Search text")):
    """Full-text search across all transcripts, returning matching segments."""
    init_db()
    session = SessionLocal()
    try:
        pattern = f"%{q}%"

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

        for transcript, recording in transcript_hits:
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

        return {"results": results, "query": q, "total": len(results)}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@app.get("/api/stats")
def get_stats():
    """Dashboard statistics."""
    init_db()
    session = SessionLocal()
    try:
        total = session.query(func.count(Recording.id)).scalar() or 0
        done = (
            session.query(func.count(Recording.id))
            .filter(Recording.status == "done")
            .scalar() or 0
        )
        pending = (
            session.query(func.count(Recording.id))
            .filter(Recording.status == "pending")
            .scalar() or 0
        )
        processing = (
            session.query(func.count(Recording.id))
            .filter(Recording.status == "processing")
            .scalar() or 0
        )
        errors = (
            session.query(func.count(Recording.id))
            .filter(Recording.status == "error")
            .scalar() or 0
        )
        avg_duration = (
            session.query(func.avg(Recording.duration_seconds))
            .filter(Recording.duration_seconds.isnot(None))
            .scalar()
        )
        total_segments = session.query(func.count(Segment.id)).scalar() or 0

        # Recordings per day (last 30 days)
        recordings_by_day = (
            session.query(
                func.date(Recording.created_at).label("day"),
                func.count(Recording.id).label("count"),
            )
            .group_by(func.date(Recording.created_at))
            .order_by(func.date(Recording.created_at).desc())
            .limit(30)
            .all()
        )

        return {
            "total_recordings": total,
            "by_status": {
                "done": done,
                "pending": pending,
                "processing": processing,
                "error": errors,
            },
            "avg_duration_seconds": round(avg_duration, 2) if avg_duration else None,
            "total_segments": total_segments,
            "recordings_per_day": [
                {"date": str(row.day), "count": row.count}
                for row in reversed(list(recordings_by_day))
            ],
        }
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Pipeline control
# ---------------------------------------------------------------------------


@app.get("/api/pipeline/status")
def pipeline_status():
    """Current pipeline status — is the watcher running, queue info."""
    return {
        "watcher_running": _watcher_thread is not None and _watcher_thread.is_alive(),
    }


@app.post("/api/pipeline/start")
def pipeline_start():
    """Start the folder watcher in a background thread."""
    global _watcher_thread, _watcher_observer, _watcher_stop_event

    if _watcher_thread is not None and _watcher_thread.is_alive():
        return {"message": "Watcher is already running"}

    import queue as queue_mod
    from watchdog.observers import Observer
    from transcriptor.watcher.folder_watcher import WavFileHandler, _process_file

    _watcher_stop_event.clear()
    watch_dir = Path(settings.WATCH_DIR)
    watch_dir.mkdir(parents=True, exist_ok=True)

    processing_queue: queue_mod.Queue[Path] = queue_mod.Queue()
    handler = WavFileHandler(processing_queue)
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)

    def _run():
        observer.start()
        try:
            while not _watcher_stop_event.is_set():
                try:
                    file_path = processing_queue.get(timeout=1)
                    import time
                    time.sleep(1)
                    _process_file(file_path)
                except queue_mod.Empty:
                    continue
        finally:
            observer.stop()
            observer.join()

    _watcher_observer = observer
    _watcher_thread = threading.Thread(target=_run, daemon=True, name="folder-watcher")
    _watcher_thread.start()

    return {"message": "Watcher started", "watch_dir": str(watch_dir)}


@app.post("/api/pipeline/stop")
def pipeline_stop():
    """Stop the folder watcher."""
    global _watcher_thread, _watcher_observer, _watcher_stop_event

    if _watcher_thread is None or not _watcher_thread.is_alive():
        return {"message": "Watcher is not running"}

    _watcher_stop_event.set()
    _watcher_thread.join(timeout=5)
    _watcher_thread = None
    _watcher_observer = None

    return {"message": "Watcher stopped"}


# ---------------------------------------------------------------------------
# WebSocket for progress
# ---------------------------------------------------------------------------

from fastapi import WebSocket, WebSocketDisconnect


@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    """WebSocket endpoint for real-time progress updates."""
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            # Keep connection alive, listen for client pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.remove(websocket)


async def broadcast_progress(message: dict):
    """Broadcast a progress message to all connected WebSocket clients."""
    import json
    disconnected = []
    for ws in _ws_clients:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _ws_clients.remove(ws)


# ---------------------------------------------------------------------------
# Static files for frontend (production)
# ---------------------------------------------------------------------------


_frontend_dir = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"


def mount_static(app_instance: FastAPI):
    """Mount frontend static assets and SPA fallback."""
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse

    if not _frontend_dir.exists():
        return

    # Serve /assets/* directly
    assets_dir = _frontend_dir / "assets"
    if assets_dir.exists():
        app_instance.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # SPA catch-all: serve index.html for any non-API route
    index_html = _frontend_dir / "index.html"

    @app_instance.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str):
        # Serve existing static files (e.g. vite.svg, favicon)
        static_file = _frontend_dir / path
        if path and static_file.exists() and static_file.is_file():
            return FileResponse(str(static_file))
        # Otherwise serve index.html for client-side routing
        return HTMLResponse(index_html.read_text())


# Mount static after all API routes are registered
mount_static(app)

"""Folder watcher that monitors a directory for new .wav files and processes them."""

import logging
import queue
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("transcriptor")


class WavFileHandler(FileSystemEventHandler):
    """Handles new .wav files appearing in the watched directory."""

    def __init__(self, processing_queue: queue.Queue):
        super().__init__()
        self.processing_queue = processing_queue

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".wav":
            logger.info(f"New WAV file detected: {path.name}")
            self.processing_queue.put(path)


def _setup_logging(log_dir: Path):
    """Configure logging to console and file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "transcriptor.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger("transcriptor")
    root_logger.setLevel(logging.INFO)
    # Avoid duplicate handlers on repeated calls
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)


def _process_file(file_path: Path):
    """Run the transcription pipeline on a single file and persist results."""
    from datetime import datetime

    from transcriptor.db.database import SessionLocal, init_db
    from transcriptor.db.models import Recording, Segment, Transcript
    from transcriptor.pipeline import TranscriptionPipeline

    init_db()
    session = SessionLocal()

    # Check if file already exists in DB
    existing = session.query(Recording).filter(Recording.filepath == str(file_path)).first()
    if existing and existing.status == "done":
        logger.info(f"Skipping already-processed file: {file_path.name}")
        session.close()
        return

    if existing:
        # Re-process a previously failed/pending recording
        recording = existing
        recording.status = "pending"
        recording.error_message = None
        session.commit()
    else:
        recording = Recording(
            filename=file_path.name,
            filepath=str(file_path),
            status="pending",
        )
        session.add(recording)
        session.commit()
    logger.info(f"Recording #{recording.id} created for {file_path.name}")

    try:
        recording.status = "processing"
        session.commit()

        pipeline = TranscriptionPipeline()
        result = pipeline.process(str(file_path))

        transcript = Transcript(
            recording_id=recording.id,
            full_text=result.full_text,
            language=result.language,
        )
        session.add(transcript)
        session.flush()

        for seg in result.segments:
            segment = Segment(
                transcript_id=transcript.id,
                speaker_label=seg.speaker,
                text=seg.text,
                start_time=seg.start,
                end_time=seg.end,
                confidence=seg.confidence,
            )
            session.add(segment)

        recording.status = "done"
        recording.duration_seconds = result.duration
        recording.processed_at = datetime.utcnow()
        session.commit()
        logger.info(f"Recording #{recording.id} processed successfully")

    except Exception as e:
        session.rollback()
        # Re-fetch to update status after rollback
        recording = session.get(Recording, recording.id)
        if recording:
            recording.status = "error"
            recording.error_message = str(e)
            session.commit()
        logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)

    finally:
        session.close()


def process_single_file(file_path: Path):
    """Public entry point to process a single WAV file."""
    _setup_logging(Path("logs"))
    logger.info(f"Processing single file: {file_path}")
    _process_file(file_path)


def process_all_unprocessed(watch_dir: Path):
    """Process all .wav files in the directory that haven't been processed yet."""
    from transcriptor.db.database import SessionLocal, init_db
    from transcriptor.db.models import Recording

    _setup_logging(Path("logs"))
    init_db()

    session = SessionLocal()
    processed_files = {r.filename for r in session.query(Recording).filter(Recording.status == "done").all()}
    session.close()

    wav_files = sorted(watch_dir.glob("*.wav"))
    unprocessed = [f for f in wav_files if f.name not in processed_files]

    if not unprocessed:
        logger.info("No unprocessed WAV files found.")
        return

    logger.info(f"Found {len(unprocessed)} unprocessed WAV file(s)")
    for f in unprocessed:
        _process_file(f)


def start_watcher(watch_dir: Path):
    """Start the folder watcher on the given directory."""
    _setup_logging(Path("logs"))

    from transcriptor.db.database import init_db

    init_db()

    watch_dir.mkdir(parents=True, exist_ok=True)
    processing_queue: queue.Queue[Path] = queue.Queue()
    handler = WavFileHandler(processing_queue)
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()
    logger.info(f"Watching {watch_dir} for new WAV files... (Ctrl+C to stop)")

    try:
        while True:
            try:
                file_path = processing_queue.get(timeout=1)
                # Brief delay to let the file finish writing
                time.sleep(1)
                _process_file(file_path)
            except queue.Empty:
                continue
    except KeyboardInterrupt:
        logger.info("Stopping watcher...")
        observer.stop()
    observer.join()

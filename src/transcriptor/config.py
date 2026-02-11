import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'transcriptions.db'}")

    # Watched folder
    WATCH_DIR: str = os.getenv("WATCH_DIR", str(Path.home() / "Downloads" / "NAGRANIA"))

    # Whisper
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "auto")
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "float16")
    WHISPER_LANGUAGE: str = os.getenv("WHISPER_LANGUAGE", "pl")

    # Pyannote
    PYANNOTE_AUTH_TOKEN: str = os.getenv("PYANNOTE_AUTH_TOKEN", "")

    # Processing
    MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "transcriptor.log"))


settings = Settings()

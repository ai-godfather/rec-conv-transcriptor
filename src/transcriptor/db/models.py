from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Recording(Base):
    __tablename__ = "recordings"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(1024), nullable=False, unique=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    status = Column(
        Enum("pending", "processing", "done", "error", name="recording_status"),
        default="pending",
        nullable=False,
    )
    error_message = Column(Text, nullable=True)

    transcripts = relationship("Transcript", back_populates="recording", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Recording(id={self.id}, filename='{self.filename}', status='{self.status}')>"


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    full_text = Column(Text, nullable=True)
    language = Column(String(10), nullable=True)
    model_used = Column(String(100), nullable=True)

    recording = relationship("Recording", back_populates="transcripts")
    segments = relationship("Segment", back_populates="transcript", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Transcript(id={self.id}, recording_id={self.recording_id}, language='{self.language}')>"


class Segment(Base):
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=False)
    speaker_label = Column(String(50), nullable=True)
    text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    confidence = Column(Float, nullable=True)

    transcript = relationship("Transcript", back_populates="segments")

    def __repr__(self):
        return f"<Segment(id={self.id}, speaker='{self.speaker_label}', start={self.start_time:.1f})>"


class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(Integer, primary_key=True)
    label = Column(String(100), nullable=False, unique=True)
    role = Column(
        Enum("agent", "customer", name="speaker_role"),
        nullable=True,
    )
    voice_sample_path = Column(String(1024), nullable=True)

    def __repr__(self):
        return f"<Speaker(id={self.id}, label='{self.label}', role='{self.role}')>"

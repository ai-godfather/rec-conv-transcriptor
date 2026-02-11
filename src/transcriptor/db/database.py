from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from transcriptor.config import settings
from transcriptor.db.models import Base

engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables (for development; use Alembic migrations in production)."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Yield a database session, ensuring it's closed after use."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

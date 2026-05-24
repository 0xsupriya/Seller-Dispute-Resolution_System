from collections.abc import Generator
from typing import Optional, Tuple

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import settings
from backend.app.models import Base

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine() -> Optional[Engine]:
    """Create the DB engine once. Returns None if DATABASE_URL is not set."""
    global _engine, _session_factory

    if not settings.database_url:
        return None

    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

    return _engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — gives each request its own DB session."""
    get_engine()
    if _session_factory is None:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")

    db = _session_factory()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> Tuple[bool, str]:
    """Run SELECT 1 to verify Neon is reachable."""
    engine = get_engine()
    if engine is None:
        return False, "DATABASE_URL is not set in .env"

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:
        return False, str(exc)


def create_tables() -> list[str]:
    """Create all tables in Neon if they do not exist yet."""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL is not set in .env")

    Base.metadata.create_all(bind=engine)
    return sorted(Base.metadata.tables.keys())


def list_tables() -> list[str]:
    """Return table names that already exist in Neon."""
    engine = get_engine()
    if engine is None:
        return []
    return sorted(inspect(engine).get_table_names())

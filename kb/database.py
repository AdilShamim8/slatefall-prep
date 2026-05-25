"""
kb/database.py
──────────────
Database connection management.

SQLite chosen over PostgreSQL because:
- Zero server setup (single file)
- ACID compliant (data won't corrupt)
- Sufficient for local assessment use
- Reviewer can run without installing any database server

If this were production at scale:
- Switch to PostgreSQL
- Add connection pooling
- Add Alembic for schema migrations
- The rest of the code would not change (SQLAlchemy abstracts the DB)
"""

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

import config
from .models import Base
from utils.logger import get_logger

logger = get_logger(__name__)

# ─── Engine ───────────────────────────────────────────────────────
_engine = None


def get_engine():
    """
    Create (or return cached) SQLAlchemy engine.
    Engine = the connection to the database file.
    Called once at startup, reused for all operations.
    """
    global _engine
    if _engine is None:
        db_url = f"sqlite:///{config.DB_PATH}"

        _engine = create_engine(
            db_url,
            # Required for SQLite to work across threads
            connect_args={"check_same_thread": False},
            # echo=True would print every SQL query — useful for debugging
            echo=False,
        )

        # Enable WAL mode for better concurrent read performance
        @event.listens_for(_engine, "connect")
        def set_wal_mode(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        logger.info(f"Database engine created: {config.DB_PATH}")

    return _engine


def init_db() -> None:
    """
    Create all tables if they don't already exist.
    Safe to call multiple times (CREATE TABLE IF NOT EXISTS).
    Call this once at application startup.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables initialized (PrepSession, QuestionResult)")


# ─── Session Factory ──────────────────────────────────────────────
def _get_session_factory() -> sessionmaker:
    """Build the session factory (called once)."""
    engine = get_engine()
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


_SessionFactory = None


def get_session_factory() -> sessionmaker:
    """Return (cached) session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        init_db()
        _SessionFactory = _get_session_factory()
    return _SessionFactory


@contextmanager
def get_db_session():
    """
    Context manager that provides a database session.
    Automatically commits on success, rolls back on error.

    Usage:
        with get_db_session() as db:
            db.add(some_object)
            # commit happens automatically on exit

    WHY context manager:
    Ensures the session is always closed, even if an exception is raised.
    Prevents connection leaks.
    """
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error(f"DB session rolled back due to: {exc}")
        raise
    finally:
        session.close()
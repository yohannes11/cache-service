"""Database engine and per-request sessions."""

from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def build_engine(database_url: str, echo: bool = False) -> Engine:
    connect_args = {}
    if database_url.startswith("sqlite"):
        # FastAPI runs sync endpoints in a thread pool, while SQLite by
        # default only allows the creating thread to use a connection.
        connect_args["check_same_thread"] = False
    return create_engine(database_url, echo=echo, connect_args=connect_args)


settings = get_settings()
engine = build_engine(settings.database_url, settings.db_echo)


def create_db_and_tables() -> None:
    # Fine for a small service; a real deployment would use Alembic
    # migrations so schema changes are versioned (documented shortcut).
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards.

    Tests replace this dependency to point at an in-memory database.
    """
    with Session(engine) as session:
        yield session

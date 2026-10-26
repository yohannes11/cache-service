"""Shared fixtures: an isolated in-memory database and a counting transformer."""

import os

# Must be set before `app` is imported so the module-level engine never
# points at a real database file.
os.environ.setdefault("CACHE_DATABASE_URL", "sqlite://")

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.transformer import get_transformer


class CountingTransformer:
    """Records every value it is asked to transform."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, value: str) -> str:
        self.seen.append(value)
        return value.upper()

    @property
    def calls(self) -> int:
        return len(self.seen)


@pytest.fixture
def engine():
    # StaticPool keeps one connection, so every session sees the same
    # in-memory database (otherwise each connection gets an empty one).
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()


@pytest.fixture
def client(engine, transformer) -> Iterator[TestClient]:
    """The real app, with the database and transformer swapped for test doubles."""

    def _session_override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_transformer] = lambda: transformer
    yield TestClient(app)
    app.dependency_overrides.clear()


SAMPLE_REQUEST = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
SAMPLE_OUTPUT = "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"

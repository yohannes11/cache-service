"""Database tables.

Two tables, one per kind of reuse the task asks for:

* ``TransformCache``: one row per distinct input string, so a string that
  appears in *any* earlier request is never sent to the transformer again.
* ``Payload``: one row per distinct (list_1, list_2) pair, so repeating the
  same request returns the same identifier instead of creating a duplicate.
"""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TransformCache(SQLModel, table=True):
    __tablename__ = "transform_cache"

    # Keyed by a SHA-256 of the input rather than the raw text: index entries
    # stay a fixed 64 chars, and PostgreSQL's B-tree rejects very long keys.
    input_hash: str = Field(primary_key=True, max_length=64)
    input_value: str
    output_value: str
    created_at: datetime = Field(default_factory=_utcnow)


class Payload(SQLModel, table=True):
    __tablename__ = "payload"

    id: int | None = Field(default=None, primary_key=True)
    # Fingerprint of the request body. The unique constraint is what makes
    # "reuse the identifier" safe even when two identical requests race.
    request_hash: str = Field(unique=True, index=True, max_length=64)
    # The finished output is stored so GET is a single primary-key lookup
    # and never depends on the transformer being reachable.
    output: str
    created_at: datetime = Field(default_factory=_utcnow)

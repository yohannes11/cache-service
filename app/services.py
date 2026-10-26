"""Business logic: build payloads while calling the transformer as little as possible.

This module knows nothing about HTTP, so it can be unit-tested directly and
reused by other entry points (a worker, a CLI) without FastAPI.
"""

import hashlib
import json
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import Payload, TransformCache
from app.schemas import PayloadRequest
from app.transformer import Transformer

OUTPUT_SEPARATOR = ", "
# Stay well below SQLite's limit on bound parameters per statement.
_LOOKUP_CHUNK = 500


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint_request(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """Stable identity of a request body.

    JSON-encoding the pair keeps list boundaries, so ["a,b"] and ["a", "b"]
    can never collide the way a naive string join would.
    """
    canonical = json.dumps([list(list_1), list(list_2)], ensure_ascii=False, separators=(",", ":"))
    return sha256_hex(canonical)


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    # strict=True turns a length mismatch into an error instead of silently
    # dropping items; the schema already guards this, so it is a safety net.
    return [item for pair in zip(first, second, strict=True) for item in pair]


def _lookup_cached(session: Session, hashes: list[str]) -> dict[str, str]:
    """Return {input_hash: output_value} for the hashes already cached."""
    found: dict[str, str] = {}
    for start in range(0, len(hashes), _LOOKUP_CHUNK):
        chunk = hashes[start : start + _LOOKUP_CHUNK]
        rows = session.exec(select(TransformCache).where(TransformCache.input_hash.in_(chunk)))
        found.update({row.input_hash: row.output_value for row in rows})
    return found


def _store_cached(session: Session, rows: list[dict]) -> None:
    """Insert new cache rows, ignoring ones another request inserted first.

    "Insert or ignore" avoids failing a request just because a concurrent
    request transformed the same string a moment earlier.
    """
    if not rows:
        return
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        stmt = postgresql.insert(TransformCache).values(rows)
    elif dialect == "sqlite":
        stmt = sqlite.insert(TransformCache).values(rows)
    else:  # pragma: no cover - only SQLite and PostgreSQL are supported
        raise RuntimeError(f"Unsupported database dialect: {dialect}")
    session.exec(stmt.on_conflict_do_nothing(index_elements=["input_hash"]))


def transform_with_cache(
    session: Session, values: Iterable[str], transformer: Transformer
) -> dict[str, str]:
    """Map each distinct value to its transformed form.

    The transformer is called at most once per distinct string, and never
    for strings seen in any earlier request.
    """
    unique_values = list(dict.fromkeys(values))  # de-duplicate, keep order
    hash_of = {value: sha256_hex(value) for value in unique_values}

    cached = _lookup_cached(session, list(hash_of.values()))
    results = {value: cached[h] for value, h in hash_of.items() if h in cached}

    now = datetime.now(timezone.utc)
    new_rows = []
    for value in unique_values:
        if value in results:
            continue
        output = transformer(value)
        results[value] = output
        new_rows.append(
            {"input_hash": hash_of[value], "input_value": value, "output_value": output, "created_at": now}
        )

    _store_cached(session, new_rows)
    # Commit now so the transformer results are kept even if saving the
    # payload itself fails below; those calls were the expensive part.
    session.commit()
    return results


def create_payload(
    session: Session, request: PayloadRequest, transformer: Transformer
) -> tuple[Payload, bool]:
    """Return (payload, created). ``created`` is False when an identical
    request was processed before and its identifier is reused."""
    request_hash = fingerprint_request(request.list_1, request.list_2)

    existing = _find_by_hash(session, request_hash)
    if existing is not None:
        # Same input, same answer: no transformer calls at all.
        return existing, False

    transformed = transform_with_cache(session, [*request.list_1, *request.list_2], transformer)
    ordered = interleave(
        [transformed[v] for v in request.list_1],
        [transformed[v] for v in request.list_2],
    )
    payload = Payload(request_hash=request_hash, output=OUTPUT_SEPARATOR.join(ordered))
    session.add(payload)
    try:
        session.commit()
    except IntegrityError:
        # An identical request committed between our lookup and insert;
        # the unique constraint caught it, so return the winner's row.
        session.rollback()
        winner = _find_by_hash(session, request_hash)
        if winner is None:  # pragma: no cover - would mean a different integrity error
            raise
        return winner, False

    session.refresh(payload)
    return payload, True


def get_payload(session: Session, payload_id: int) -> Payload | None:
    return session.get(Payload, payload_id)


def _find_by_hash(session: Session, request_hash: str) -> Payload | None:
    return session.exec(select(Payload).where(Payload.request_hash == request_hash)).first()

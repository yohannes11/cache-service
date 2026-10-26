"""Unit tests for the business logic, without HTTP."""

import pytest
from sqlmodel import select

from app import services
from app.models import Payload, TransformCache
from app.schemas import PayloadRequest
from tests.conftest import SAMPLE_OUTPUT, SAMPLE_REQUEST


def test_interleave_alternates_items():
    assert services.interleave(["a", "c"], ["b", "d"]) == ["a", "b", "c", "d"]


def test_interleave_rejects_uneven_lists():
    with pytest.raises(ValueError):
        services.interleave(["a"], ["b", "c"])


def test_fingerprint_is_stable_and_respects_list_boundaries():
    assert services.fingerprint_request(["a"], ["b"]) == services.fingerprint_request(["a"], ["b"])
    # A naive ",".join would make these two requests collide.
    assert services.fingerprint_request(["a,b"], ["c"]) != services.fingerprint_request(["a", "b"], ["c"])
    # Swapping the lists changes the output order, so it is a different payload.
    assert services.fingerprint_request(["a"], ["b"]) != services.fingerprint_request(["b"], ["a"])


def test_transform_calls_transformer_once_per_distinct_value(session, transformer):
    result = services.transform_with_cache(session, ["x", "y", "x", "x"], transformer)

    assert result == {"x": "X", "y": "Y"}
    assert transformer.seen == ["x", "y"]


def test_transform_reuses_cached_results(session, transformer):
    services.transform_with_cache(session, ["x", "y"], transformer)
    services.transform_with_cache(session, ["y", "z"], transformer)

    assert transformer.seen == ["x", "y", "z"]  # "y" came from the cache
    assert len(session.exec(select(TransformCache)).all()) == 3


def test_create_payload_builds_expected_output(session, transformer):
    payload, created = services.create_payload(session, PayloadRequest(**SAMPLE_REQUEST), transformer)

    assert created is True
    assert payload.output == SAMPLE_OUTPUT


def test_identical_request_reuses_identifier_without_transforming(session, transformer):
    request = PayloadRequest(**SAMPLE_REQUEST)
    first, _ = services.create_payload(session, request, transformer)
    calls_after_first = transformer.calls

    second, created = services.create_payload(session, request, transformer)

    assert created is False
    assert second.id == first.id
    assert transformer.calls == calls_after_first
    assert len(session.exec(select(Payload)).all()) == 1


def test_get_payload_returns_none_for_unknown_id(session):
    assert services.get_payload(session, 12345) is None

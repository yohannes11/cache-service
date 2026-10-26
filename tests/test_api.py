"""Integration tests: real HTTP routing, validation and database, fake transformer."""

from tests.conftest import SAMPLE_OUTPUT, SAMPLE_REQUEST


def test_create_then_read_matches_spec_example(client):
    created = client.post("/payload", json=SAMPLE_REQUEST)
    assert created.status_code == 201
    body = created.json()
    assert body["created"] is True

    fetched = client.get(f"/payload/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == {"output": SAMPLE_OUTPUT}


def test_repeated_request_returns_same_id_with_200(client, transformer):
    first = client.post("/payload", json=SAMPLE_REQUEST).json()
    calls_after_first = transformer.calls

    second = client.post("/payload", json=SAMPLE_REQUEST)

    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert second.json()["created"] is False
    assert transformer.calls == calls_after_first


def test_new_payload_only_transforms_unseen_strings(client, transformer):
    client.post("/payload", json=SAMPLE_REQUEST)
    transformer.seen.clear()

    response = client.post(
        "/payload", json={"list_1": ["first string", "brand new"], "list_2": ["last string", "first string"]}
    )

    assert response.status_code == 201
    assert transformer.seen == ["brand new"]
    output = client.get(f"/payload/{response.json()['id']}").json()["output"]
    assert output == "FIRST STRING, LAST STRING, BRAND NEW, FIRST STRING"


def test_lists_of_different_length_are_rejected(client, transformer):
    response = client.post("/payload", json={"list_1": ["a", "b"], "list_2": ["c"]})

    assert response.status_code == 422
    assert "same length" in response.text
    assert transformer.calls == 0


def test_missing_field_is_rejected(client):
    assert client.post("/payload", json={"list_1": ["a"]}).status_code == 422


def test_unknown_payload_returns_404(client):
    assert client.get("/payload/999").status_code == 404


def test_non_integer_id_is_rejected(client):
    assert client.get("/payload/abc").status_code == 422


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}

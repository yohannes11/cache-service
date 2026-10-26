"""CLI tests: argument parsing on its own, then the full CLI against the app."""

import io
import json

import pytest
from pydantic import ValidationError

from cli.main import load_request, main, parse_args, run
from tests.conftest import SAMPLE_OUTPUT, SAMPLE_REQUEST


def test_short_flags_are_parsed():
    settings = parse_args(["-h", "http://example.com:9000", "-r", "3", "-j", "{}", "-o", "out.jsonl"])

    assert settings.base_url == "http://example.com:9000"
    assert settings.repeat == 3
    assert settings.json_body == "{}"
    assert settings.output == "out.jsonl"


def test_long_flags_and_defaults():
    settings = parse_args(["--input", "-"])

    assert settings.base_url == "http://localhost:8000"
    assert settings.repeat == 1
    assert settings.input == "-"
    assert settings.output == "-"


@pytest.mark.parametrize(
    "argv",
    [
        [],  # no input source
        ["-i", "a.json", "-j", "{}"],  # two input sources
        ["-j", "{}", "-r", "0"],  # repeat must be positive
        ["-j", "{}", "-h", "not a url"],
    ],
)
def test_invalid_arguments_are_rejected(argv):
    with pytest.raises(ValidationError):
        parse_args(argv)


def test_load_request_from_stdin():
    settings = parse_args(["-i", "-"])
    request = load_request(settings, io.StringIO(json.dumps(SAMPLE_REQUEST)))
    assert request.list_1 == SAMPLE_REQUEST["list_1"]


def test_load_request_from_file(tmp_path):
    path = tmp_path / "body.json"
    path.write_text(json.dumps(SAMPLE_REQUEST))
    request = load_request(parse_args(["-i", str(path)]), io.StringIO())
    assert request.list_2 == SAMPLE_REQUEST["list_2"]


def test_invalid_body_exits_with_code_2(capsys):
    assert main(["-j", '{"list_1": ["a"], "list_2": []}']) == 2
    assert "invalid input" in capsys.readouterr().err


def test_run_end_to_end_against_app(client, transformer):
    # TestClient is an httpx.Client, so the CLI talks to the real app in-process.
    settings = parse_args(["-h", "http://testserver", "-r", "3", "-j", json.dumps(SAMPLE_REQUEST)])
    out = io.StringIO()

    results = run(settings, client, load_request(settings, io.StringIO()), out)

    lines = [json.loads(line) for line in out.getvalue().splitlines()]
    assert lines == results
    assert [r["created"] for r in results] == [True, False, False]
    assert {r["id"] for r in results} == {results[0]["id"]}
    assert all(r["output"] == SAMPLE_OUTPUT for r in results)
    assert transformer.calls == 6  # only the first iteration hit the transformer

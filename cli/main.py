"""cache-cli: exercise the caching service from the command line.

    cache-cli [-h|--host URL] [-r|--repeat N] [-i|--input FILE|-]
              [-j|--json JSON] [-o|--output FILE|-] [--help]

The spec gives ``-h`` to both --host and --help. A flag can only mean one
thing, so ``-h`` is --host (the more frequently typed option) and help is
available as ``--help``.
"""

import argparse
import json
import sys
import time
from typing import Any, TextIO

import httpx
from pydantic import AliasChoices, AnyHttpUrl, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, CliApp, CliSettingsSource, SettingsConfigDict

from app.schemas import PayloadRequest

STDIO = "-"


class CliSettings(BaseSettings):
    """Command-line options. Pydantic Settings parses and validates them, so
    bad input is rejected with a clear message before any request is sent."""

    model_config = SettingsConfigDict(
        cli_prog_name="cache-cli",
        # Env vars like CACHE_CLI_HOST can provide defaults (handy in Docker);
        # the prefix stops a generic $HOST from leaking in.
        env_prefix="CACHE_CLI_",
        cli_enforce_required=False,
    )

    host: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:8000"),
        validation_alias=AliasChoices("h", "host"),
        description="Base URL of the caching service.",
    )
    repeat: int = Field(
        default=1,
        ge=1,
        le=10_000,
        validation_alias=AliasChoices("r", "repeat"),
        description="How many times to send the request (shows cache reuse).",
    )
    input: str | None = Field(
        default=None,
        validation_alias=AliasChoices("i", "input"),
        description="File with the JSON request body, or '-' for stdin.",
    )
    json_body: str | None = Field(
        default=None,
        validation_alias=AliasChoices("j", "json"),
        description="Request body as a JSON string (quote it for your shell).",
    )
    output: str = Field(
        default=STDIO,
        validation_alias=AliasChoices("o", "output"),
        description="Where to write results (JSON lines), or '-' for stdout.",
    )

    @field_validator("input", "output")
    @classmethod
    def strip_paths(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def exactly_one_source(self) -> "CliSettings":
        if (self.input is None) == (self.json_body is None):
            raise ValueError("provide exactly one of --input or --json")
        return self

    @property
    def base_url(self) -> str:
        return str(self.host).rstrip("/")


def parse_args(argv: list[str]) -> CliSettings:
    # Our own argparse root parser with add_help=False frees up "-h" for
    # --host; "--help" is added back explicitly.
    parser = argparse.ArgumentParser(prog="cache-cli", add_help=False, description=__doc__.splitlines()[0])
    parser.add_argument("--help", action="help", help="Show this message and exit.")
    source = CliSettingsSource(CliSettings, root_parser=parser)
    return CliApp.run(CliSettings, cli_args=argv, cli_settings_source=source)


def load_request(settings: CliSettings, stdin: TextIO) -> PayloadRequest:
    """Read the body from --json, a file or stdin and validate it locally,
    so malformed input fails fast instead of as a server 422."""
    if settings.json_body is not None:
        raw = settings.json_body
    elif settings.input == STDIO:
        raw = stdin.read()
    else:
        with open(settings.input, encoding="utf-8") as fh:
            raw = fh.read()
    return PayloadRequest.model_validate_json(raw)


def run(settings: CliSettings, client: httpx.Client, request: PayloadRequest, out: TextIO) -> list[dict[str, Any]]:
    """POST then GET, ``repeat`` times. Each result is written as one JSON line.

    Timing each POST makes the effect of the cache visible: the first call
    may hit the transformer, repeats should not.
    """
    results = []
    body = request.model_dump()
    for iteration in range(1, settings.repeat + 1):
        started = time.perf_counter()
        created = client.post(f"{settings.base_url}/payload", json=body)
        created.raise_for_status()
        post_ms = (time.perf_counter() - started) * 1000

        info = created.json()
        fetched = client.get(f"{settings.base_url}/payload/{info['id']}")
        fetched.raise_for_status()

        result = {
            "iteration": iteration,
            "id": info["id"],
            "created": info["created"],
            "output": fetched.json()["output"],
            "post_ms": round(post_ms, 2),
        }
        out.write(json.dumps(result, ensure_ascii=False) + "\n")
        results.append(result)
    return results


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        settings = parse_args(argv)
        request = load_request(settings, sys.stdin)
    except (ValidationError, ValueError, OSError) as exc:
        print(f"cache-cli: invalid input: {exc}", file=sys.stderr)
        return 2

    try:
        with httpx.Client(timeout=30) as client:
            if settings.output == STDIO:
                run(settings, client, request, sys.stdout)
            else:
                with open(settings.output, "w", encoding="utf-8") as fh:
                    run(settings, client, request, fh)
    except httpx.HTTPStatusError as exc:
        print(f"cache-cli: server returned {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"cache-cli: could not reach {settings.base_url}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Caching Service

A small FastAPI microservice that builds "payloads" from two lists of strings and
caches the results of an expensive transformer function, plus a CLI to exercise it.

```
POST /payload   {"list_1": [...], "list_2": [...]}  ->  {"id": 1, "created": true, "message": "..."}
GET  /payload/1                                      ->  {"output": "FIRST STRING, OTHER STRING, ..."}
```

Interactive API docs are at `http://localhost:8000/docs` once the service runs.

## How caching works

| Reuse | Where | Effect |
|---|---|---|
| Transformer results | `transform_cache` table, keyed by SHA-256 of the input string | A string seen in **any** earlier request is never transformed again. Within one request each distinct string is transformed once. |
| Payload identifiers | `payload` table, unique `request_hash` of the request body | Sending the same lists again returns the existing id (HTTP 200 instead of 201) with zero transformer calls. |

Cache lookups are one `SELECT ... WHERE input_hash IN (...)` per request (chunked),
and new rows are written with `INSERT ... ON CONFLICT DO NOTHING` so concurrent
requests for the same string don't fail. A race between two identical payload
requests is resolved by the unique constraint on `request_hash`.

## Project layout

```
app/
  main.py         FastAPI app, startup hook, /health
  api.py          HTTP routes (thin: validate -> service -> response)
  services.py     Business logic: caching, interleaving, id reuse
  models.py       Database tables (SQLModel)
  schemas.py      Request/response bodies (Pydantic)
  db.py           Engine and per-request session dependency
  transformer.py  The "external service" stand-in
  config.py       Settings from environment variables
cli/main.py       cache-cli
tests/            Unit (services), integration (API) and CLI tests
```

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload                       # SQLite file ./cache.db
```

## Running with Docker

```bash
docker compose up --build          # API + PostgreSQL on http://localhost:8000
# or, SQLite only:
docker build -t cache-service . && docker run -p 8000:8000 cache-service
```

## CLI

```bash
cache-cli -j '{"list_1":["first string","second string"],"list_2":["other string","another string"]}'
cache-cli --host http://localhost:8000 --repeat 5 --input body.json --output results.jsonl
cat body.json | cache-cli -i -
cache-cli --help
```

Each iteration POSTs the body, GETs the result and prints one JSON line with the
id, whether it was newly created, the output and the POST latency. With `--repeat`
you can see the second and later calls reuse the id.

Exit codes: `0` success, `1` server/network error, `2` invalid arguments or input.

## Tests

```bash
pytest
```

Tests use an in-memory SQLite database and a fake transformer that counts calls,
injected through FastAPI's `dependency_overrides`. The CLI tests drive the real
app in-process because `TestClient` is an `httpx.Client`.

## Decisions and shortcuts

- **`-h` means `--host`.** The spec assigns `-h` to both host and help; a flag can
  only mean one thing, so help is `--help`.
- **Output is stored on the payload row.** GET is one primary-key lookup and keeps
  working even if the transformer is down. Cost: a little duplicated storage.
- **Empty lists are rejected** (422). Interleaving nothing is technically valid,
  but an empty payload is far more likely a client bug.
- **Tables are created at startup** with `create_all` instead of Alembic
  migrations. Fine for this task; a production service should version its schema.
- **Sync endpoints.** SQLModel sessions are synchronous; FastAPI runs sync
  endpoints in a thread pool, so they don't block the event loop.
- **The transformer is an uppercase function** with an optional artificial delay,
  standing in for the external service described in the task.

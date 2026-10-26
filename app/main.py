"""Application entry point: ``uvicorn app.main:app``."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.db import create_db_and_tables


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Runs once at startup, before the first request is accepted.
    create_db_and_tables()
    yield


app = FastAPI(
    title="Caching Service",
    description="Builds interleaved payloads and caches transformer results.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    # Used by the Docker healthcheck; deliberately does not touch the DB.
    return {"status": "ok"}

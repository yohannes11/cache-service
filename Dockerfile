FROM python:3.12-slim

# No .pyc files in the image, and logs appear immediately in `docker logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Copy only what the install needs first, so Docker can reuse the
# dependency layer when only application code changes.
COPY pyproject.toml ./
COPY app ./app
COPY cli ./cli
RUN pip install .

# Don't run the service as root inside the container.
RUN useradd --create-home appuser && mkdir -p /srv/data && chown appuser /srv/data
USER appuser

ENV CACHE_DATABASE_URL=sqlite:////srv/data/cache.db
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

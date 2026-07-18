# Single image for both api and worker services (ADR-06).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Install deps first for layer caching.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install .

# App source + built dashboard static (dashboard/dist mounted into app static at build time).
COPY app ./app

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# Single image for both api and worker services (ADR-06).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Create a secure non-root user and group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/bash appuser

WORKDIR /srv

# Install runtime dependencies (e.g., curl/wget for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl wget && \
    rm -rf /var/lib/apt/lists/*

# Install deps first for layer caching.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install .

# App source + built dashboard static
COPY app ./app
COPY ops/healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh

# Change ownership to the non-root user
RUN chown -R appuser:appgroup /srv

# Switch to the non-root user
USER appuser

EXPOSE 8000

# Configure Docker healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD /usr/local/bin/healthcheck.sh

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

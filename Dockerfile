# Stage 1: Build the virtual environment
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# 1. Install build dependencies first (Permanently cached)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1

# 2. Copy only requirements to cache Python libraries
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 3. Copy source code and sync project (Rebuilds only on code changes)
COPY src ./src
COPY README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
RUN uv sync --frozen --no-dev

# ---

# Stage 2: Create a stable runtime base
FROM python:3.12-slim-bookworm AS runtime-base

# 1. Install runtime dependencies first (FFmpeg is heavy, cache it!)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Setup user and directories
RUN groupadd bot && useradd -g bot -u 1000 -d /app bot \
    && mkdir -p /app/data /app/sessions /app/logs /app/backups \
    && chown -R bot:bot /app

# ---

# Stage 3: Final application image
FROM runtime-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Simply pull the heavy /app folder from the builder
COPY --from=builder --chown=bot:bot /app /app

USER bot
CMD ["python3", "-m", "src.main"]

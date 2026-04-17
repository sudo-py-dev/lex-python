# Stage 1: Build the virtual environment
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set the working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy only requirements to leverage Docker caching for dependencies
COPY pyproject.toml uv.lock ./

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies without installing the project itself
RUN uv sync --frozen --no-install-project --no-dev

# Copy the source code and other required files
COPY src ./src
COPY scripts ./scripts
COPY README.md ./
COPY alembic.ini ./
COPY alembic ./alembic

# Install the project
RUN uv sync --frozen --no-dev

# ---

# Stage 2: Create a stable runtime base with system dependencies
# This stage stays CACHED even when you change your bot's source code.
FROM python:3.12-slim-bookworm AS runtime-base

WORKDIR /app

# Install runtime dependencies (ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create a non-privileged user and group
RUN groupadd bot && useradd -g bot -u 1000 -d /app bot

# Create directories for persistent data and set ownership
RUN mkdir -p /app/data /app/sessions /app/logs /app/backups \
    && chown -R bot:bot /app

# ---

# Stage 3: Final application image
# This stage is rebuilt instantly because it only copies from the builder.
FROM runtime-base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy the pre-built environment and project from the builder
COPY --from=builder --chown=bot:bot /app /app

# Switch to the non-privileged user
USER bot

# Run the bot
CMD ["python3", "-m", "src.main"]

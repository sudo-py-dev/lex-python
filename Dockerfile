# Use a specialized uv image for building
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies without installing the project itself
RUN uv sync --frozen --no-install-project --no-dev

# Copy source code and scripts
COPY src ./src
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini .
COPY README.md .

# Install the project
RUN uv sync --frozen --no-dev


# Final lightweight image
FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy virtual environment and project from builder
COPY --from=builder /app /app

# Create a non-root user for security
RUN groupadd -r botgroup && useradd -r -g botgroup botuser \
    && chown -R botuser:botgroup /app \
    && mkdir -p /app/sessions /app/logs \
    && chown -R botuser:botgroup /app/sessions /app/logs

# Switch to non-root user
USER botuser

# Expose no ports as it's a bot

# Use a shell script to run migrations and then start the bot
CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]

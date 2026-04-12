# Use the official uv image for building
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set the working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy project files
COPY pyproject.toml uv.lock ./

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies without installing the project itself
# This layer will be cached if dependencies don't change
RUN uv sync --frozen --no-install-project --no-dev

# Copy the source code
COPY src ./src
COPY scripts ./scripts
COPY README.md ./
COPY alembic.ini ./
COPY alembic ./alembic

# Install the project
RUN uv sync --frozen --no-dev

# Final stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy the installed project and environment from the builder
COPY --from=builder /app /app

# Add the virtualenv bin directory to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create directories for persistent data
RUN mkdir -p /app/data /app/sessions /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create a non-privileged user and group
RUN groupadd -r bot && useradd -r -g bot -u 1000 -d /app bot

# Set ownership for the application directory
RUN chown -R bot:bot /app

# Switch to the non-privileged user
USER bot

# Use entrypoint script to run migrations before starting the bot
CMD ["python3", "-m", "src.main"]

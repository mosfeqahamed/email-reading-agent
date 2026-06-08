# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Bring in the uv binary from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (cached layer) using the lockfile.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Then copy the application code.
COPY app/ ./app/
COPY data/ ./data/

# Put the virtualenv on PATH so we can call python/uvicorn directly.
ENV PATH="/app/.venv/bin:$PATH"

# Default command runs the agent; compose overrides it for the dashboard.
CMD ["python", "-m", "app.agent"]

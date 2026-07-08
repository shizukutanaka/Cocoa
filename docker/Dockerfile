# Multi-stage build: frontend/dist is baked into the final image so
# main/api_server.py's StaticFiles mount + SPA fallback route (see
# _is_frontend_dist_available() in main/api_server.py) actually has
# something to serve -- previously this Dockerfile never built or copied
# the frontend at all.

# ---------------------------------------------------------------------------
# Stage 1: build the frontend (Vite + React + TS SPA)
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Only what compiling/running the reachable modules' dependencies actually
# needs (libpq for psycopg2/SQLAlchemy's postgres driver, libffi/libssl for
# cryptography, gcc/g++ to build any of them from sdist on an architecture
# without a prebuilt wheel). curl is for the HEALTHCHECK below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# requirements-ci.txt, not requirements.txt: the latter also installs
# torch/transformers/diffusers/web3/oqs/pqcrystals/sklearn for the ~60 main/
# modules that are not reachable from either real entry point (api_server.py,
# main.py) -- see FEATURE_AUDIT.md 4-1 and requirements-ci.txt's own header
# for how the reachable set was determined. None of that is needed to run
# the app that actually ships, and skipping it keeps this image small and
# avoids compiling several packages that need extra system libraries this
# image doesn't otherwise install.
COPY requirements-ci.txt .
RUN pip install --upgrade pip && pip install -r requirements-ci.txt

# Application code. Only main/ is needed at runtime (the ~60 unreachable
# modules under main/ ship too, since they're not separated out today, but
# nothing imports them) plus the frontend's built output from stage 1.
COPY main/ ./main/
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Create non-root user
RUN useradd --create-home --shell /bin/bash cocoa && chown -R cocoa:cocoa /app
USER cocoa

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "main.api_server:app", "--host", "0.0.0.0", "--port", "8000"]

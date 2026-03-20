# =============================================================================
# Open Mission Control — Multi-stage Dockerfile
#
# Runs all 4 processes (Convex, Next.js, MC Gateway, Nanobot Gateway) in one
# container. Named stages allow extracting individual services later.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: base — System dependencies (Node.js 20, Python 3.12, system tools)
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg git lsof && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get purge -y gnupg && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# ---------------------------------------------------------------------------
# Stage 2: python-deps — Install Python dependencies (cached layer)
# ---------------------------------------------------------------------------
FROM base AS python-deps

# Copy only dependency manifests and minimal vendor stubs
COPY pyproject.toml uv.lock ./
COPY vendor/nanobot/pyproject.toml vendor/nanobot/
COPY vendor/claude-code/pyproject.toml vendor/claude-code/

# Create minimal package stubs so uv can resolve editable installs.
# boot.py is a single-file module (not a package) — stub it as a file.
# nanobot's pyproject.toml has force-include for bridge → nanobot/bridge.
RUN mkdir -p mc tmux_claude_control \
        vendor/nanobot/nanobot vendor/nanobot/bridge vendor/claude-code/claude_code && \
    touch mc/__init__.py tmux_claude_control/__init__.py boot.py \
        vendor/nanobot/nanobot/__init__.py vendor/claude-code/claude_code/__init__.py

RUN uv sync --frozen

# ---------------------------------------------------------------------------
# Stage 3: node-deps — Install Node.js dependencies (cached layer)
# ---------------------------------------------------------------------------
FROM python-deps AS node-deps

COPY dashboard/package.json dashboard/package-lock.json dashboard/
RUN cd dashboard && npm ci

# ---------------------------------------------------------------------------
# Stage 4: runtime — Full application + Convex initialization
# ---------------------------------------------------------------------------
FROM node-deps AS runtime

# Remove python-deps stubs before copying real source
RUN rm -rf mc/ tmux_claude_control/ boot.py

# Copy all source code (node_modules preserved — excluded by .dockerignore)
COPY mc/ mc/
COPY boot.py boot.py
COPY shared/ shared/
COPY vendor/ vendor/
COPY dashboard/ dashboard/
COPY agent_docs/ agent_docs/
COPY Makefile Makefile
COPY scripts/docker-entrypoint.sh scripts/docker-entrypoint.sh
COPY scripts/init-convex.sh scripts/init-convex.sh

# Re-sync so uv sees real source (editable installs point to actual code)
RUN uv sync --frozen

# Create config directory
RUN mkdir -p /root/.nanobot

# Initialize Convex schema and bake template database
RUN chmod +x scripts/init-convex.sh scripts/docker-entrypoint.sh && \
    bash scripts/init-convex.sh

# Ports: Next.js(3000) Convex(3210) ConvexSite(3211) Interactive(8765) Nanobot(18790)
EXPOSE 3000 3210 3211 8765 18790

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

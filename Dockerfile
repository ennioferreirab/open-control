# =============================================================================
# Open Control — Multi-stage Dockerfile
#
# Runs all processes (Convex, Next.js, MC Gateway) in one container.
# Named stages allow extracting individual services later.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: base — System dependencies (Node.js 20, Python 3.12, system tools)
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg git lsof tmux && \
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
COPY vendor/claude-code/pyproject.toml vendor/claude-code/

# Create minimal package stubs so uv can resolve editable installs.
RUN mkdir -p mc vendor/claude-code/claude_code && \
    touch mc/__init__.py vendor/claude-code/claude_code/__init__.py

RUN uv sync --frozen

# ---------------------------------------------------------------------------
# Stage 3: node-deps — Install Node.js dependencies (cached layer)
# ---------------------------------------------------------------------------
FROM python-deps AS node-deps

COPY dashboard/package.json dashboard/package-lock.json dashboard/
RUN cd dashboard && npm ci

# Pre-resolve the Hermes ACP harness so the first hermes dispatch does not pay
# the uvx cold-start (env resolution + download). The [mcp] extra is required
# for Hermes to connect to the stdio MCP servers we pass on session/new.
# Inherited by both the dev and runtime stages, so it applies to mc and mc-test.
RUN uvx --from 'hermes-agent[acp,mcp]==0.15.2' hermes-acp --version

# ---------------------------------------------------------------------------
# Stage: dev — Dependencies + CLI tools (source code bind-mounted at runtime)
# ---------------------------------------------------------------------------
FROM node-deps AS dev

# Install Claude Code CLI — required by provider-cli strategy to spawn agent sessions
# Symlink to /root/.local/bin so the native-install check passes inside containers
RUN npm install -g @anthropic-ai/claude-code && \
    mkdir -p /root/.local/bin && \
    ln -sf $(which claude) /root/.local/bin/claude

# Create config directory
RUN mkdir -p /root/.open-control

# Ports: Next.js(3000) Convex(3210) ConvexSite(3211) Interactive(8765)
EXPOSE 3000 3210 3211 8765

# No ENTRYPOINT — source/scripts are bind-mounted; entrypoint set in docker-compose.yml

# ---------------------------------------------------------------------------
# Stage: runtime — Full application + Convex initialization (CI / production)
# ---------------------------------------------------------------------------
FROM node-deps AS runtime

# Remove python-deps stubs before copying real source
RUN rm -rf mc/

# Copy all source code (node_modules preserved — excluded by .dockerignore)
COPY mc/ mc/
COPY shared/ shared/
COPY vendor/ vendor/
COPY dashboard/ dashboard/
COPY agent_docs/ agent_docs/
COPY Makefile Makefile
COPY scripts/docker-entrypoint.sh scripts/docker-entrypoint.sh
COPY scripts/init-convex.sh scripts/init-convex.sh

# Re-sync so uv sees real source (editable installs point to actual code)
RUN uv sync --frozen

# Install Claude Code CLI — required by provider-cli strategy to spawn agent sessions
RUN npm install -g @anthropic-ai/claude-code

# Create config directory
RUN mkdir -p /root/.open-control

# Initialize Convex schema and bake template database
RUN chmod +x scripts/init-convex.sh scripts/docker-entrypoint.sh && \
    bash scripts/init-convex.sh

# Ports: Next.js(3000) Convex(3210) ConvexSite(3211) Interactive(8765)
EXPOSE 3000 3210 3211 8765

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

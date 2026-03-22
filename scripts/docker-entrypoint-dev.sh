#!/bin/bash
# Dev container entrypoint for Open Control.
# Handles volume-mounted source: re-links Python editable installs,
# initializes node_modules if empty, and starts the stack.
set -e

# ─── Generate .env.local files ──────────────────────────────────
CONVEX_DEPLOYMENT="${CONVEX_DEPLOYMENT:-anonymous:anonymous-dashboard}"
CONVEX_URL="${CONVEX_URL:-http://127.0.0.1:3210}"
CONVEX_SITE_URL="${CONVEX_SITE_URL:-http://127.0.0.1:3211}"

cat > /app/dashboard/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
NEXT_PUBLIC_CONVEX_URL=${CONVEX_URL}
NEXT_PUBLIC_CONVEX_SITE_URL=${CONVEX_SITE_URL}
EOF

cat > /app/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
CONVEX_URL=${CONVEX_URL}
CONVEX_SITE_URL=${CONVEX_SITE_URL}
EOF

# ─── Remove stale PID file from previous container run ───────────
rm -f /root/.nanobot/mc.pid

# ─── Re-link Python editable installs (~1s) ─────────────────────
echo "[dev] Syncing Python dependencies..."
uv sync --frozen 2>&1 | tail -3

# ─── Initialize node_modules if volume is empty (first run) ─────
if [ ! -f /app/dashboard/node_modules/.package-lock.json ]; then
    echo "[dev] Installing Node dependencies (first run, ~30s)..."
    cd /app/dashboard && npm ci
    cd /app
else
    echo "[dev] Node dependencies already installed."
fi

# ─── Initialize Convex from baked template if fresh ──────────────
if [ ! -f /app/dashboard/.convex/local/default/convex_local_backend.sqlite3 ]; then
    echo "[dev] Initializing fresh Convex from template..."
    mkdir -p /app/dashboard/.convex/local
    cp -r /app/.convex-template/local/default /app/dashboard/.convex/local/default
fi

# ─── Deploy Convex functions before starting the stack ────────────
# Ensures functions are available when the gateway queries Convex.
# --once starts an embedded backend, pushes functions, then exits.
echo "[dev] Deploying Convex functions..."
cd /app/dashboard && npx convex dev --local --once 2>&1 | tail -5
cd /app

# ─── Start the stack ─────────────────────────────────────────────
echo "[dev] Starting Open Control..."
exec /app/.venv/bin/nanobot mc start "$@"

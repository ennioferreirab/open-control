#!/bin/bash
# Container entrypoint for Open Control.
# Generates .env.local files and initializes Convex — from baked template
# (runtime image) or from schema (dev image with bind-mounted source).
set -e

# Allow overrides via environment variables, default to container-local Convex
CONVEX_DEPLOYMENT="${CONVEX_DEPLOYMENT:-anonymous:anonymous-dashboard}"
CONVEX_URL="${CONVEX_URL:-http://127.0.0.1:3210}"
CONVEX_SITE_URL="${CONVEX_SITE_URL:-http://127.0.0.1:3211}"

# Generate .env.local for dashboard (Next.js)
cat > /app/dashboard/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
NEXT_PUBLIC_CONVEX_URL=${CONVEX_URL}
NEXT_PUBLIC_CONVEX_SITE_URL=${CONVEX_SITE_URL}
NEXT_PUBLIC_INTERACTIVE_PORT=${NEXT_PUBLIC_INTERACTIVE_PORT:-8765}
EOF

# Generate .env.local for Python backend
cat > /app/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
CONVEX_URL=${CONVEX_URL}
CONVEX_SITE_URL=${CONVEX_SITE_URL}
EOF

# Initialize Convex if no database exists yet
if [ ! -f /app/dashboard/.convex/local/default/convex_local_backend.sqlite3 ]; then
    if [ -d /app/.convex-template/local ]; then
        # Runtime image: restore from baked template (fast)
        echo "[entrypoint] Initializing fresh Convex from template..."
        mkdir -p /app/dashboard/.convex/local
        cp -r /app/.convex-template/local/default /app/dashboard/.convex/local/default
    else
        # Dev image: no template, initialize from schema (first run only)
        echo "[entrypoint] No template found, initializing Convex from schema..."
        cd /app/dashboard
        npx convex dev --local --once
        cd /app
    fi
fi

# Remove stale PID file from previous container run
rm -f /root/.nanobot/mc.pid

# Start the full stack — use venv binary directly (no uv run overhead)
exec /app/.venv/bin/nanobot mc start "$@"

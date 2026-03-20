#!/bin/bash
# Container entrypoint for Open Mission Control.
# Generates .env.local files and initializes Convex from the baked template
# if this is a fresh start (no existing database volume).
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
EOF

# Generate .env.local for Python backend
cat > /app/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
CONVEX_URL=${CONVEX_URL}
CONVEX_SITE_URL=${CONVEX_SITE_URL}
EOF

# Initialize Convex from baked template if fresh start
if [ ! -f /app/dashboard/.convex/local/default/convex_local_backend.sqlite3 ]; then
    echo "[entrypoint] Initializing fresh Convex from template..."
    mkdir -p /app/dashboard/.convex/local
    cp -r /app/dashboard/.convex-template/local/default /app/dashboard/.convex/local/default
fi

# Start the full stack — use venv binary directly (no uv run overhead)
exec /app/.venv/bin/nanobot mc start "$@"

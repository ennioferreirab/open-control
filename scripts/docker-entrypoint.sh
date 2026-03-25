#!/bin/bash
# Container entrypoint for Open Control.
# Generates .env.local files and initializes Convex.
#
# Convex mode: cloud by default, pass --local for local Convex backend.
set -e

# ─── Detect Convex mode ──────────────────────────────────────
CONVEX_LOCAL=false
MC_EXTRA_ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--local" ]; then
        CONVEX_LOCAL=true
    else
        MC_EXTRA_ARGS+=("$arg")
    fi
done

# ─── Set Convex env defaults based on mode ─────────────────────
if [ "$CONVEX_LOCAL" = true ]; then
    CONVEX_DEPLOYMENT="${CONVEX_DEPLOYMENT:-anonymous:anonymous-dashboard}"
    CONVEX_URL="${CONVEX_URL:-http://127.0.0.1:3210}"
    CONVEX_SITE_URL="${CONVEX_SITE_URL:-http://127.0.0.1:3211}"
else
    if [ -z "${CONVEX_DEPLOYMENT:-}" ] || [ -z "${CONVEX_URL:-}" ]; then
        echo "[entrypoint] ERROR: CONVEX_DEPLOYMENT and CONVEX_URL must be set for cloud mode."
        echo "[entrypoint] Pass --local to use local Convex backend instead."
        exit 1
    fi
    CONVEX_SITE_URL="${CONVEX_SITE_URL:-}"
fi

# Generate .env.local for dashboard (Next.js)
cat > /app/dashboard/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
NEXT_PUBLIC_CONVEX_URL=${CONVEX_URL}
NEXT_PUBLIC_CONVEX_SITE_URL=${CONVEX_SITE_URL}
NEXT_PUBLIC_INTERACTIVE_PORT=${NEXT_PUBLIC_INTERACTIVE_PORT:-8765}
EOF

if [ -n "${CONVEX_ADMIN_KEY:-}" ]; then
    echo "CONVEX_ADMIN_KEY=${CONVEX_ADMIN_KEY}" >> /app/dashboard/.env.local
fi

# Generate .env.local for Python backend
cat > /app/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
CONVEX_URL=${CONVEX_URL}
CONVEX_SITE_URL=${CONVEX_SITE_URL}
EOF

# ─── Convex initialization ────────────────────────────────────────
if [ "$CONVEX_LOCAL" = false ]; then
    echo "[entrypoint] Deploying Convex functions (cloud)..."
    cd /app/dashboard && npx convex dev --once 2>&1 | tail -10
    cd /app
fi

if [ "$CONVEX_LOCAL" = true ]; then
    if [ ! -f /app/dashboard/.convex/local/default/convex_local_backend.sqlite3 ]; then
        if [ -d /app/.convex-template/local ]; then
            echo "[entrypoint] Initializing fresh Convex from template..."
            mkdir -p /app/dashboard/.convex/local
            cp -r /app/.convex-template/local/default /app/dashboard/.convex/local/default
        else
            echo "[entrypoint] No template found, initializing Convex from schema..."
            cd /app/dashboard
            npx convex dev --local --local-force-upgrade --once
            cd /app
        fi
    fi
fi

# Remove stale PID file from previous container run
rm -f /root/.nanobot/mc.pid

# Start the full stack
if [ "$CONVEX_LOCAL" = true ]; then
    exec /app/.venv/bin/nanobot mc start --local "${MC_EXTRA_ARGS[@]}"
else
    exec /app/.venv/bin/nanobot mc start "${MC_EXTRA_ARGS[@]}"
fi

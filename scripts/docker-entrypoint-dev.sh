#!/bin/bash
# Dev container entrypoint for Open Control.
# Handles volume-mounted source: re-links Python editable installs,
# initializes node_modules if empty, and starts the stack.
#
# Convex mode: cloud by default, pass --local for local Convex backend.
set -e

# ─── Sync host credentials into runtime home ──────────────────
if [ -n "${OPEN_CONTROL_HOME:-}" ]; then
    echo "[dev] Using OPEN_CONTROL_HOME=${OPEN_CONTROL_HOME}"
    mkdir -p "${OPEN_CONTROL_HOME}/workspace"
    # Symlink Convex CLI state so `npx convex` finds auth at ~/.convex
    if [ -d "${OPEN_CONTROL_HOME}/.convex" ] && [ ! -d /root/.convex ]; then
        ln -sf "${OPEN_CONTROL_HOME}/.convex" /root/.convex
    fi
else
    # Legacy: copy from read-only host mounts into container volume
    echo "[dev] Syncing host config into runtime volume..."
    mkdir -p /root/.nanobot/workspace
    for f in config.json secrets.json; do
        if [ -f "/root/.nanobot-host/$f" ]; then
            cp "/root/.nanobot-host/$f" "/root/.nanobot/$f"
        fi
    done
    if [ -d /root/.nanobot-host/workspace ]; then
        cp -r /root/.nanobot-host/workspace/. /root/.nanobot/workspace/
    fi
fi

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

# ─── Generate .env.local files ──────────────────────────────────
if [ "$CONVEX_LOCAL" = true ]; then
    echo "[dev] Convex mode: LOCAL"
    CONVEX_DEPLOYMENT="${CONVEX_DEPLOYMENT:-anonymous:anonymous-dashboard}"
    CONVEX_URL="${CONVEX_URL:-http://127.0.0.1:3210}"
    CONVEX_SITE_URL="${CONVEX_SITE_URL:-http://127.0.0.1:3211}"
    PUBLIC_CONVEX_URL="${NEXT_PUBLIC_CONVEX_URL:-${CONVEX_URL}}"
    PUBLIC_CONVEX_SITE_URL="${NEXT_PUBLIC_CONVEX_SITE_URL:-${CONVEX_SITE_URL}}"
else
    echo "[dev] Convex mode: CLOUD"
    # Cloud mode requires these env vars to be set
    if [ -z "${CONVEX_DEPLOYMENT:-}" ] || [ -z "${CONVEX_URL:-}" ]; then
        echo "[dev] ERROR: CONVEX_DEPLOYMENT and CONVEX_URL must be set for cloud mode."
        echo "[dev] Pass --local to use local Convex backend instead."
        exit 1
    fi
    CONVEX_SITE_URL="${CONVEX_SITE_URL:-}"
    PUBLIC_CONVEX_URL="${NEXT_PUBLIC_CONVEX_URL:-${CONVEX_URL}}"
    PUBLIC_CONVEX_SITE_URL="${NEXT_PUBLIC_CONVEX_SITE_URL:-${CONVEX_SITE_URL}}"
fi

cat > /app/dashboard/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
CONVEX_URL=${CONVEX_URL}
NEXT_PUBLIC_CONVEX_URL=${PUBLIC_CONVEX_URL}
NEXT_PUBLIC_CONVEX_SITE_URL=${PUBLIC_CONVEX_SITE_URL}
NEXT_PUBLIC_INTERACTIVE_PORT=${NEXT_PUBLIC_INTERACTIVE_PORT:-8765}
EOF

# Inject admin key if provided
if [ -n "${CONVEX_ADMIN_KEY:-}" ]; then
    echo "CONVEX_ADMIN_KEY=${CONVEX_ADMIN_KEY}" >> /app/dashboard/.env.local
fi

cat > /app/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
CONVEX_URL=${CONVEX_URL}
CONVEX_SITE_URL=${CONVEX_SITE_URL}
EOF

# ─── Seed Claude Code global config from host (skip onboarding) ──
# Only copy essential fields — strip hooks, native install refs, host paths.
if [ -f /root/.host-claude.json ] && [ ! -f /root/.claude.json ]; then
    python3 -c "
import json
with open('/root/.host-claude.json') as f:
    host = json.load(f)
sanitized = {
    'hasCompletedOnboarding': True,
    'lastOnboardingVersion': host.get('lastOnboardingVersion', '2.1.0'),
    'oauthAccount': host.get('oauthAccount'),
    'userID': host.get('userID'),
    'opusProMigrationComplete': True,
    'sonnet1m45MigrationComplete': True,
    'installMethod': 'npm',
}
sanitized = {k: v for k, v in sanitized.items() if v is not None}
with open('/root/.claude.json', 'w') as f:
    json.dump(sanitized, f, indent=2)
" && echo "[dev] Seeded sanitized Claude Code config"
fi

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

# ─── Convex initialization ────────────────────────────────────────
if [ "$CONVEX_LOCAL" = false ]; then
    # Cloud mode: push functions to cloud deployment before starting
    echo "[dev] Deploying Convex functions (cloud)..."
    cd /app/dashboard && npx convex dev --once 2>&1 | tail -10
    cd /app
fi

if [ "$CONVEX_LOCAL" = true ]; then
    # Initialize Convex from baked template if fresh
    if [ ! -f /app/dashboard/.convex/local/default/convex_local_backend.sqlite3 ]; then
        if [ -d /app/.convex-template/local/default ]; then
            echo "[dev] Initializing fresh Convex from template..."
            mkdir -p /app/dashboard/.convex/local
            cp -r /app/.convex-template/local/default /app/dashboard/.convex/local/default
        else
            echo "[dev] No Convex template found — will initialize from schema..."
        fi
    fi

    # Deploy Convex functions locally before starting the stack
    echo "[dev] Deploying Convex functions (local)..."
    cd /app/dashboard && npx convex dev --local --local-force-upgrade --once 2>&1 | tail -5
    cd /app

    # Inject Convex admin key from local config
    CONVEX_CONFIG="/app/dashboard/.convex/local/default/config.json"
    if [ -z "${CONVEX_ADMIN_KEY:-}" ] && [ -f "$CONVEX_CONFIG" ]; then
        CONVEX_ADMIN_KEY=$(python3 -c "import json; print(json.load(open('$CONVEX_CONFIG')).get('adminKey',''))" 2>/dev/null)
    fi
    if [ -n "${CONVEX_ADMIN_KEY:-}" ]; then
        grep -q "CONVEX_ADMIN_KEY" /app/dashboard/.env.local 2>/dev/null || \
            echo "CONVEX_ADMIN_KEY=${CONVEX_ADMIN_KEY}" >> /app/dashboard/.env.local
        echo "[dev] CONVEX_ADMIN_KEY injected into dashboard .env.local"
    fi

    # Fix public Convex URL for port-mapped containers
    if [ "${PUBLIC_CONVEX_URL}" != "${CONVEX_URL}" ]; then
        echo "[dev] Public Convex URL override: ${PUBLIC_CONVEX_URL}"
    fi
fi

# ─── Start the stack ─────────────────────────────────────────────
if [ "$CONVEX_LOCAL" = true ]; then
    echo "[dev] Starting Open Control (local Convex)..."
    exec /app/.venv/bin/nanobot mc start --local "${MC_EXTRA_ARGS[@]}"
else
    echo "[dev] Starting Open Control (cloud Convex)..."
    exec /app/.venv/bin/nanobot mc start "${MC_EXTRA_ARGS[@]}"
fi

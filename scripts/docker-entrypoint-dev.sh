#!/bin/bash
# Dev container entrypoint for Open Control.
# Handles volume-mounted source: re-links Python editable installs,
# initializes node_modules if empty, and starts the stack.
set -e

# ─── Generate .env.local files ──────────────────────────────────
CONVEX_DEPLOYMENT="${CONVEX_DEPLOYMENT:-anonymous:anonymous-dashboard}"
CONVEX_URL="${CONVEX_URL:-http://127.0.0.1:3210}"
CONVEX_SITE_URL="${CONVEX_SITE_URL:-http://127.0.0.1:3211}"
# Browser connects via host-mapped port; defaults to internal URL if not set
PUBLIC_CONVEX_URL="${NEXT_PUBLIC_CONVEX_URL:-${CONVEX_URL}}"
PUBLIC_CONVEX_SITE_URL="${NEXT_PUBLIC_CONVEX_SITE_URL:-${CONVEX_SITE_URL}}"

cat > /app/dashboard/.env.local << EOF
CONVEX_DEPLOYMENT=${CONVEX_DEPLOYMENT}
CONVEX_URL=${CONVEX_URL}
NEXT_PUBLIC_CONVEX_URL=${PUBLIC_CONVEX_URL}
NEXT_PUBLIC_CONVEX_SITE_URL=${PUBLIC_CONVEX_SITE_URL}
NEXT_PUBLIC_INTERACTIVE_PORT=${NEXT_PUBLIC_INTERACTIVE_PORT:-8765}
EOF

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
    if [ -d /app/.convex-template/local/default ]; then
        echo "[dev] Initializing fresh Convex from template..."
        mkdir -p /app/dashboard/.convex/local
        cp -r /app/.convex-template/local/default /app/dashboard/.convex/local/default
    else
        echo "[dev] No Convex template found — will initialize from schema..."
    fi
fi

# ─── Deploy Convex functions before starting the stack ────────────
# Ensures functions are available when the gateway queries Convex.
# --once starts an embedded backend, pushes functions, then exits.
echo "[dev] Deploying Convex functions..."
cd /app/dashboard && npx convex dev --local --once 2>&1 | tail -5
cd /app

# ─── Inject Convex admin key into dashboard .env.local ─────────────
# Must run AFTER convex deploy (which creates config.json with adminKey).
CONVEX_CONFIG="/app/dashboard/.convex/local/default/config.json"
if [ -z "${CONVEX_ADMIN_KEY:-}" ] && [ -f "$CONVEX_CONFIG" ]; then
    CONVEX_ADMIN_KEY=$(python3 -c "import json; print(json.load(open('$CONVEX_CONFIG')).get('adminKey',''))" 2>/dev/null)
fi
if [ -n "${CONVEX_ADMIN_KEY:-}" ]; then
    grep -q "CONVEX_ADMIN_KEY" /app/dashboard/.env.local 2>/dev/null || \
        echo "CONVEX_ADMIN_KEY=${CONVEX_ADMIN_KEY}" >> /app/dashboard/.env.local
    echo "[dev] CONVEX_ADMIN_KEY injected into dashboard .env.local"
fi

# ─── Fix public Convex URL for port-mapped containers ──────────────
if [ "${PUBLIC_CONVEX_URL}" != "${CONVEX_URL}" ]; then
    echo "[dev] Public Convex URL override: ${PUBLIC_CONVEX_URL}"
fi

# ─── Start the stack ─────────────────────────────────────────────
echo "[dev] Starting Open Control..."
exec /app/.venv/bin/nanobot mc start "$@"

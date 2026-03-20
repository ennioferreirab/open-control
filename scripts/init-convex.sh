#!/bin/bash
# Build-time Convex initialization.
# Runs `convex dev --local --once` to start the local backend, push schema,
# then snapshots the initialized database to .convex-template/ so containers
# start with a baked baseline.
set -e

DASHBOARD_DIR="/app/dashboard"

echo "[init-convex] Generating .env.local for build-time Convex..."
cat > "$DASHBOARD_DIR/.env.local" << 'EOF'
CONVEX_DEPLOYMENT=anonymous:anonymous-dashboard
NEXT_PUBLIC_CONVEX_URL=http://127.0.0.1:3210
NEXT_PUBLIC_CONVEX_SITE_URL=http://127.0.0.1:3211
EOF

echo "[init-convex] Pushing schema to local Convex backend..."
cd "$DASHBOARD_DIR"

# convex dev --local --once starts an embedded backend, pushes schema, then exits
npx convex dev --local --once

# Validate that the database was created
if [ ! -f "$DASHBOARD_DIR/.convex/local/default/convex_local_backend.sqlite3" ]; then
    echo "[init-convex] ERROR: Convex database not found after schema push"
    exit 1
fi

echo "[init-convex] Snapshotting initialized database to .convex-template/..."
mkdir -p "$DASHBOARD_DIR/.convex-template"
cp -r "$DASHBOARD_DIR/.convex/local/" "$DASHBOARD_DIR/.convex-template/local/"

# Validate the template was baked correctly
if [ ! -f "$DASHBOARD_DIR/.convex-template/local/default/convex_local_backend.sqlite3" ]; then
    echo "[init-convex] ERROR: Template database not found after snapshot"
    exit 1
fi

# Clean up runtime state so the image doesn't ship with a live database
rm -rf "$DASHBOARD_DIR/.convex/local"

echo "[init-convex] Done. Template baked at .convex-template/"

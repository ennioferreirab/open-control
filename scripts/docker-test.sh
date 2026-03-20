#!/bin/bash
# Spin up an isolated Docker test instance for the current worktree.
# Finds available ports, starts the container, waits for health, prints URLs.
#
# Usage:
#   scripts/docker-test.sh          # start
#   scripts/docker-test.sh down     # stop
#   scripts/docker-test.sh status   # check health
set -e

# Derive a unique container name from the git branch or directory
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || basename "$PWD")
CONTAINER_NAME="mc-test-${BRANCH//\//-}"

# --- Subcommands ---

if [ "${1:-}" = "down" ]; then
    echo "[docker-test] Stopping $CONTAINER_NAME..."
    docker stop "$CONTAINER_NAME" 2>/dev/null && docker rm "$CONTAINER_NAME" 2>/dev/null || true
    echo "[docker-test] Stopped."
    exit 0
fi

if [ "${1:-}" = "status" ]; then
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        PORTS=$(docker port "$CONTAINER_NAME" 2>/dev/null)
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
        echo "[docker-test] Container: $CONTAINER_NAME (health: $HEALTH)"
        echo "$PORTS"
    else
        echo "[docker-test] No running container: $CONTAINER_NAME"
    fi
    exit 0
fi

# --- Find available ports ---

find_free_port() {
    local start=${1:-3100}
    local port=$start
    while [ $port -lt $((start + 100)) ]; do
        if ! lsof -ti :"$port" > /dev/null 2>&1; then
            echo "$port"
            return 0
        fi
        port=$((port + 1))
    done
    echo "ERROR: no free port found starting from $start" >&2
    return 1
}

NEXT_PORT=$(find_free_port 3100)
CONVEX_PORT=$(find_free_port 3300)
CONVEX_SITE_PORT=$((CONVEX_PORT + 1))

echo "[docker-test] Ports: dashboard=$NEXT_PORT convex=$CONVEX_PORT"

# --- Build if image doesn't exist ---

IMAGE_NAME="mc-test:latest"
if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo "[docker-test] Building image (first time)..."
    docker build -t "$IMAGE_NAME" .
else
    echo "[docker-test] Image $IMAGE_NAME exists. Rebuild with: docker build -t $IMAGE_NAME ."
fi

# --- Stop existing container if running ---

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[docker-test] Stopping existing $CONTAINER_NAME..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

# --- Start container ---

echo "[docker-test] Starting $CONTAINER_NAME..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "${NEXT_PORT}:3000" \
    -p "${CONVEX_PORT}:3210" \
    -p "${CONVEX_SITE_PORT}:3211" \
    -v /tmp/mc-test-${BRANCH//\//-}:/root/.nanobot \
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    -e MC_ACCESS_TOKEN="${MC_ACCESS_TOKEN:-}" \
    --health-cmd "curl -sf http://localhost:3000 && curl -sf http://localhost:3210/version" \
    --health-interval 15s \
    --health-timeout 10s \
    --health-retries 10 \
    --health-start-period 90s \
    "$IMAGE_NAME"

# --- Wait for health ---

echo "[docker-test] Waiting for stack to start (first request triggers Next.js compilation)..."
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    # Check if container is still running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "[docker-test] ERROR: Container exited unexpectedly. Logs:"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        exit 1
    fi

    # Trigger Next.js compilation and check readiness
    if curl -sf -m 10 "http://localhost:${NEXT_PORT}" -o /dev/null 2>/dev/null; then
        echo ""
        echo "============================================"
        echo "  Stack ready! ($((WAITED))s)"
        echo ""
        echo "  Dashboard:  http://localhost:${NEXT_PORT}"
        echo "  Convex:     http://localhost:${CONVEX_PORT}"
        echo "  Container:  $CONTAINER_NAME"
        echo ""
        echo "  Stop with:  make docker-test-down"
        echo "============================================"
        exit 0
    fi

    printf "."
    sleep 5
    WAITED=$((WAITED + 5))
done

echo ""
echo "[docker-test] WARNING: Dashboard not ready after ${MAX_WAIT}s. Container is running."
echo "  Dashboard:  http://localhost:${NEXT_PORT}"
echo "  Convex:     http://localhost:${CONVEX_PORT}"
echo "  Container:  $CONTAINER_NAME"
echo "  Check logs: docker logs $CONTAINER_NAME"

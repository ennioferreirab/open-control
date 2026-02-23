#!/bin/bash
# reboot_nanobot.sh — Fully restarts nanobot
# Usage: bash reboot_nanobot.sh
# Can be called by the agent itself after installing new skills

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[reboot] Stopping nanobot at: $SCRIPT_DIR"
cd "$SCRIPT_DIR"

uv run nanobot mc down

echo "[reboot] Waiting 3 seconds..."
sleep 3

echo "[reboot] Starting nanobot..."
uv run nanobot mc start

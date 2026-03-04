#!/bin/bash
# Minimal test: does the MCP tool register?
set -euo pipefail
unset CLAUDECODE 2>/dev/null || true

BRIDGE_DIR="$(cd "$(dirname "$0")" && pwd)"
TMPDIR="${TMPDIR:-/tmp}"
CONFIG_FILE=$(mktemp "${TMPDIR}/ask-bridge-test.XXXXXX.json")

cat > "$CONFIG_FILE" <<EOF
{
  "mcpServers": {
    "askbridge": {
      "command": "node",
      "args": ["${BRIDGE_DIR}/server.mjs"]
    }
  }
}
EOF

echo "=== Test 1: Simple prompt (no ask_user needed) ==="
echo "MCP config: $CONFIG_FILE"
echo ""

# First test: just see if Claude can see the tool
claude -p "List all available MCP tools you have access to. Just list the tool names, nothing else." \
  --output-format text \
  --mcp-config "$CONFIG_FILE" \
  --max-turns 2 \
  2>/tmp/ask-bridge-stderr.log

echo ""
echo "=== Stderr ==="
cat /tmp/ask-bridge-stderr.log

rm -f "$CONFIG_FILE"

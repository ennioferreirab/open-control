#!/bin/bash
# Test: Does --permission-prompt-tool intercept AskUserQuestion?
#
# This test runs claude -p with a prompt designed to trigger AskUserQuestion,
# routing all permission decisions through our MCP server.
# The log file will reveal whether AskUserQuestion reaches the MCP server.

set -euo pipefail

# Allow running from within a Claude Code session
unset CLAUDECODE 2>/dev/null || true
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/permission_log.jsonl"
OUTPUT_FILE="$SCRIPT_DIR/claude_output.json"

# Clean previous logs
rm -f "$LOG_FILE" "$OUTPUT_FILE"
echo "=== Test: permission-prompt-tool AskUserQuestion interception ==="
echo "Log file: $LOG_FILE"
echo ""

# MCP config pointing to our Python server
MCP_CONFIG=$(cat <<'EOF'
{
  "mcpServers": {
    "permbridge": {
      "command": "/opt/homebrew/bin/python3",
      "args": ["SCRIPT_DIR_PLACEHOLDER/permission_server.py"]
    }
  }
}
EOF
)
MCP_CONFIG="${MCP_CONFIG//SCRIPT_DIR_PLACEHOLDER/$SCRIPT_DIR}"

# Prompt designed to naturally trigger AskUserQuestion
# Claude Code's AskUserQuestion is used when it needs user preferences
PROMPT='You need to create a simple config file for me. But FIRST, you MUST ask me (using AskUserQuestion) which format I prefer: JSON, YAML, or TOML. Do NOT proceed without asking. Do NOT guess. Use the AskUserQuestion tool to ask me. After I answer, just tell me what I chose — do not actually create any file.'

echo "Running claude -p with permission-prompt-tool..."
echo "Prompt: $PROMPT"
echo ""

# Run claude in headless mode with our permission bridge
claude -p "$PROMPT" \
  --output-format json \
  --mcp-config "$MCP_CONFIG" \
  --permission-prompt-tool mcp__permbridge__permission_prompt \
  --max-turns 5 \
  --verbose \
  2>"$SCRIPT_DIR/stderr.log" \
  | tee "$OUTPUT_FILE"

echo ""
echo ""
echo "=== RESULTS ==="
echo ""

echo "--- Claude output ---"
if [ -f "$OUTPUT_FILE" ]; then
  python3 -c "
import json, sys
try:
    data = json.load(open('$OUTPUT_FILE'))
    print(f\"Result: {data.get('result', 'N/A')[:500]}\")
    print(f\"Session: {data.get('session_id', 'N/A')}\")
    print(f\"Turns: {data.get('num_turns', 'N/A')}\")
    print(f\"Cost: \${data.get('total_cost_usd', 'N/A')}\")
except Exception as e:
    print(f'Error parsing output: {e}')
    print(open('$OUTPUT_FILE').read()[:500])
"
fi

echo ""
echo "--- Permission log (what the MCP server saw) ---"
if [ -f "$LOG_FILE" ]; then
  echo "Total entries: $(wc -l < "$LOG_FILE")"
  echo ""
  # Show all permission_request and ASK_USER events
  python3 -c "
import json
with open('$LOG_FILE') as f:
    for line in f:
        entry = json.loads(line)
        event = entry.get('event', '')
        if event in ('permission_request', 'ASK_USER_INTERCEPTED', 'auto_allow'):
            print(json.dumps(entry, indent=2, ensure_ascii=False))
        elif event == 'raw_message':
            print(f\"  [msg] method={entry.get('method')} id={entry.get('id')}\")
"
  echo ""
  echo "--- Key question: Did AskUserQuestion reach the MCP server? ---"
  if grep -q "ASK_USER_INTERCEPTED" "$LOG_FILE"; then
    echo ">>> YES! AskUserQuestion was intercepted by permission-prompt-tool <<<"
    echo ">>> Approach 1 is VIABLE! <<<"
  elif grep -q "AskUserQuestion" "$LOG_FILE"; then
    echo ">>> AskUserQuestion appeared in logs but may not have been fully intercepted <<<"
    echo ">>> Check the full log for details <<<"
  else
    echo ">>> NO. AskUserQuestion did NOT reach the MCP server <<<"
    echo ">>> Approach 1 does NOT work. Need Approach 2 (custom MCP tool). <<<"
  fi
else
  echo "No log file found — MCP server may not have started"
fi

echo ""
echo "--- Full log (for debugging) ---"
[ -f "$LOG_FILE" ] && cat "$LOG_FILE"
echo ""
echo "--- Stderr ---"
[ -f "$SCRIPT_DIR/stderr.log" ] && tail -20 "$SCRIPT_DIR/stderr.log"

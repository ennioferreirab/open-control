#!/bin/bash
#
# claude-ask: Wrapper that runs claude -p with interactive ask_user support.
#
# Usage:
#   claude-ask "Your prompt here" [extra claude flags...]
#
# This wrapper:
#   1. Creates named pipes for bidirectional communication
#   2. Starts claude -p with the ask-bridge MCP server configured
#   3. When Claude calls ask_user, displays the question in your terminal
#   4. Collects your answer and sends it back to Claude
#   5. Uses your Claude subscription (no API key needed)
#
set -euo pipefail

# Allow running from within a Claude Code session
unset CLAUDECODE 2>/dev/null || true

BRIDGE_DIR="$(cd "$(dirname "$0")" && pwd)"
TMPDIR="${TMPDIR:-/tmp}"
PIPE_DIR=$(mktemp -d "${TMPDIR}/ask-bridge.XXXXXX")
Q_PIPE="${PIPE_DIR}/questions"
A_PIPE="${PIPE_DIR}/answers"

# Create named pipes
mkfifo "$Q_PIPE"
mkfifo "$A_PIPE"

cleanup() {
  rm -rf "$PIPE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

if [ $# -lt 1 ]; then
  echo "Usage: claude-ask \"Your prompt here\" [extra claude flags...]"
  exit 1
fi

PROMPT="$1"
shift

# MCP config for this session
MCP_CONFIG=$(cat <<EOF
{
  "mcpServers": {
    "askbridge": {
      "command": "node",
      "args": ["${BRIDGE_DIR}/server.mjs"],
      "env": {
        "ASK_BRIDGE_Q_PIPE": "${Q_PIPE}",
        "ASK_BRIDGE_A_PIPE": "${A_PIPE}"
      }
    }
  }
}
EOF
)

# Write MCP config to a temp file (avoids shell quoting issues with --mcp-config)
MCP_CONFIG_FILE="${PIPE_DIR}/mcp-config.json"
echo "$MCP_CONFIG" > "$MCP_CONFIG_FILE"

# System prompt addition telling Claude to use ask_user
ASK_PROMPT='IMPORTANT: You do NOT have the AskUserQuestion tool. Instead, use the MCP tool "mcp__askbridge__ask_user" whenever you need to ask the user a question, get their preference, or need any user input before proceeding. This tool works identically to AskUserQuestion: pass 1-4 questions, each with a header, question text, and 2-4 options. The user can also type free-text answers.'

# Start the question handler in the background
handle_questions() {
  while true; do
    # Read question from the pipe (blocks until MCP server writes)
    if ! QUESTION=$(cat "$Q_PIPE" 2>/dev/null); then
      break
    fi

    [ -z "$QUESTION" ] && continue

    echo "" >&2
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
    echo "  Claude is asking you a question:" >&2
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2

    # Parse and display questions
    ANSWERS="{}"
    NUM_Q=$(echo "$QUESTION" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['questions']))")

    for i in $(seq 0 $((NUM_Q - 1))); do
      Q_TEXT=$(echo "$QUESTION" | python3 -c "import sys,json; q=json.load(sys.stdin)['questions'][$i]; print(q['question'])")
      Q_HEADER=$(echo "$QUESTION" | python3 -c "import sys,json; q=json.load(sys.stdin)['questions'][$i]; print(q.get('header',''))")
      MULTI=$(echo "$QUESTION" | python3 -c "import sys,json; q=json.load(sys.stdin)['questions'][$i]; print(q.get('multiSelect',False))")

      echo "" >&2
      echo "  [$Q_HEADER] $Q_TEXT" >&2
      echo "" >&2

      # Display options
      OPTS=$(echo "$QUESTION" | python3 -c "
import sys, json
q = json.load(sys.stdin)['questions'][$i]
for j, o in enumerate(q.get('options', []), 1):
    print(f\"  {j}. {o['label']} — {o.get('description', '')}\")
print(f\"  {len(q.get('options', []))+1}. (Type your own answer)\")
")
      echo "$OPTS" >&2

      echo "" >&2
      if [ "$MULTI" = "True" ]; then
        echo -n "  Enter option number(s) separated by comma, or type answer: " >&2
      else
        echo -n "  Enter option number or type answer: " >&2
      fi

      read -r USER_INPUT < /dev/tty

      # Resolve option number to label, or use raw input
      ANSWER=$(echo "$QUESTION" | python3 -c "
import sys, json
q = json.load(sys.stdin)['questions'][$i]
opts = q.get('options', [])
user_input = '''$USER_INPUT'''.strip()
multi = q.get('multiSelect', False)

if multi:
    parts = [p.strip() for p in user_input.split(',')]
    labels = []
    for p in parts:
        try:
            idx = int(p) - 1
            if 0 <= idx < len(opts):
                labels.append(opts[idx]['label'])
            else:
                labels.append(p)
        except ValueError:
            labels.append(p)
    print(', '.join(labels))
else:
    try:
        idx = int(user_input) - 1
        if 0 <= idx < len(opts):
            print(opts[idx]['label'])
        else:
            print(user_input)
    except ValueError:
        print(user_input)
")

      echo "  → $ANSWER" >&2
      ANSWERS=$(echo "$ANSWERS" | python3 -c "
import sys, json
a = json.load(sys.stdin)
a['''$Q_TEXT'''] = '''$ANSWER'''
print(json.dumps(a))
")
    done

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
    echo "" >&2

    # Write answers back to the pipe
    echo "$ANSWERS" > "$A_PIPE"
  done
}

# Start question handler in background
handle_questions &
HANDLER_PID=$!

# Run claude with our MCP config
claude -p "$PROMPT" \
  --output-format json \
  --mcp-config "$MCP_CONFIG_FILE" \
  --append-system-prompt "$ASK_PROMPT" \
  --max-turns 10 \
  "$@"

EXIT_CODE=$?

# Cleanup
kill $HANDLER_PID 2>/dev/null || true
exit $EXIT_CODE

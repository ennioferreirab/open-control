#!/usr/bin/env python3
"""
MCP Permission Prompt Server — Test for AskUserQuestion interception.

Minimal MCP server using text-mode stdio with Content-Length framing.
"""

import json
import sys
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "permission_log.jsonl")


def log(entry: dict):
    entry["timestamp"] = datetime.now().isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[PERM] {entry.get('event', '')}: {json.dumps(entry, ensure_ascii=False)}", file=sys.stderr, flush=True)


def send(response: dict):
    """Send JSON-RPC response with Content-Length framing (byte-accurate)."""
    body_str = json.dumps(response)
    body_bytes = body_str.encode("utf-8")
    # Write header + body as raw bytes to stdout
    header = f"Content-Length: {len(body_bytes)}\r\n\r\n"
    sys.stdout.write(header + body_str)
    sys.stdout.flush()


def read_message():
    """Read one Content-Length framed message from text-mode stdin."""
    # Read lines until we find Content-Length header
    content_length = 0
    while True:
        line = sys.stdin.readline()
        if not line:
            return None  # EOF
        line = line.strip()
        if line == "":
            # Empty line = end of headers; if we have content_length, read body
            if content_length > 0:
                break
            continue
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())

    if content_length == 0:
        return None

    body = sys.stdin.read(content_length)
    if not body:
        return None

    return json.loads(body)


def handle_initialize(req_id, params):
    client_version = params.get("protocolVersion", "2024-11-05")
    log({"event": "initialize", "client_protocol": client_version})
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": client_version,  # Echo client version
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "permission-bridge-test", "version": "0.1.0"},
        },
    }


def handle_tools_list(req_id):
    log({"event": "tools/list"})
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": [
                {
                    "name": "permission_prompt",
                    "description": "Handles permission prompts from Claude Code.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "tool_name": {"type": "string"},
                            "tool_input": {"type": "object"},
                            "tool_use_id": {"type": "string"},
                        },
                        "required": ["tool_name", "tool_input"],
                    },
                }
            ]
        },
    }


def handle_tool_call(req_id, params):
    arguments = params.get("arguments", {})
    claude_tool = arguments.get("tool_name", "unknown")
    claude_input = arguments.get("tool_input", {})

    log({
        "event": "permission_request",
        "claude_tool": claude_tool,
        "claude_input": claude_input,
    })

    if claude_tool == "AskUserQuestion":
        questions = claude_input.get("questions", [])
        answers = {}
        for q in questions:
            qtxt = q.get("question", "")
            opts = q.get("options", [])
            answer = opts[0].get("label", "Option 1") if opts else "test-answer"
            answers[qtxt] = answer
            log({"event": "ASK_USER_INTERCEPTED", "question": qtxt, "answer": answer})

        payload = {"behavior": "allow", "updatedInput": {**claude_input, "answers": answers}}
    else:
        log({"event": "auto_allow", "tool": claude_tool})
        payload = {"behavior": "allow", "updatedInput": claude_input}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    }


def main():
    log({"event": "server_started"})

    while True:
        try:
            msg = read_message()
            if msg is None:
                log({"event": "stdin_closed"})
                break

            method = msg.get("method", "")
            req_id = msg.get("id")
            params = msg.get("params", {})

            log({"event": "msg", "method": method, "id": req_id})

            if req_id is None:
                continue  # Notification — no response needed

            if method == "initialize":
                resp = handle_initialize(req_id, params)
            elif method == "tools/list":
                resp = handle_tools_list(req_id)
            elif method == "tools/call":
                resp = handle_tool_call(req_id, params)
            else:
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}

            send(resp)

        except Exception as e:
            log({"event": "error", "error": str(e), "type": type(e).__name__})


if __name__ == "__main__":
    main()

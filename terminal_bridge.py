#!/usr/bin/env python3
"""
Terminal Bridge — Production-ready bridge between Convex and a local tmux/Claude session.

Architecture:
  [Convex DB] --subscribe--> [Bridge] --send-keys--> [tmux/Claude]
  [tmux/Claude] --capture-pane--> [Bridge] --mutation--> [Convex DB]

The bridge uses `ConvexBridge.subscribe()` (blocking iterator via Convex SDK WebSocket)
in a separate thread. When Convex notifies a new `pendingInput`, the bridge injects it
into tmux. When Claude responds, the bridge writes the output back to Convex.

No polling — purely event-driven on the input side.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
import signal
import socket
import subprocess
import sys
import time
import threading
import uuid
from pathlib import Path

# ── Resolve project root ───────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from nanobot.mc.bridge import ConvexBridge

# ── Constants ──────────────────────────────────────────────────────────────────
_DEFAULT_CONVEX_URL = "https://affable-clownfish-908.convex.cloud"
STABLE_SECONDS = 0.0   # seconds without output change = Claude finished
POLL_INTERVAL = 0.1    # local pane read interval (no LLM calls)


# ── IP detection ───────────────────────────────────────────────────────────────

def get_local_ip() -> str:
    """Detect the local IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


# ── CLI argument parsing ───────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Terminal Bridge: connects a local tmux/Claude session to Convex."
    )
    parser.add_argument(
        "--session-id",
        default=str(uuid.uuid4()),
        help="Unique session identifier (default: auto-generated UUID4)",
    )
    parser.add_argument(
        "--display-name",
        default="Remoto",
        help="Human-readable display name for this terminal session (default: Remoto)",
    )
    parser.add_argument(
        "--convex-url",
        default=os.environ.get("CONVEX_URL", _DEFAULT_CONVEX_URL),
        help="Convex deployment URL (default: $CONVEX_URL or hardcoded fallback)",
    )
    parser.add_argument(
        "--admin-key",
        default=os.environ.get("CONVEX_ADMIN_KEY"),
        help="Convex admin key for server-side auth (default: $CONVEX_ADMIN_KEY)",
    )
    parser.add_argument(
        "--tmux-session",
        default="claude-terminal",
        help="tmux session name (default: claude-terminal)",
    )
    return parser.parse_args()


# ── Global state (set after arg parse) ────────────────────────────────────────
# These are module-level variables populated in main() before use.
bridge: ConvexBridge
SESSION_ID: str
AGENT_NAME: str
DISPLAY_NAME: str
TMUX_SESSION: str
TMUX_PANE: str

_last_good_output: str = ""


# ── tmux helpers ───────────────────────────────────────────────────────────────

def tmux_send(text: str):
    """Send text to the tmux pane."""
    subprocess.run(["tmux", "send-keys", "-t", TMUX_PANE, text, ""], check=True)


def tmux_enter():
    """Send Enter to the tmux pane."""
    subprocess.run(["tmux", "send-keys", "-t", TMUX_PANE, "", "Enter"], check=True)


def tmux_capture() -> str:
    """Capture the current content of the tmux pane."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", TMUX_PANE, "-p", "-S", "-50"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def wait_for_claude_response() -> str:
    """
    Wait for Claude to finish responding.
    Detects stability: output hasn't changed for STABLE_SECONDS.
    Streams intermediate output to Convex so the dashboard updates in real-time.
    100% local — zero LLM calls.
    """
    print("[bridge] Waiting for Claude response...", flush=True)
    last_output = ""
    last_streamed = ""
    stable_since = None

    while True:
        current = tmux_capture()
        if current != last_output:
            last_output = current
            stable_since = time.time()
            # Stream intermediate output to Convex for real-time dashboard updates
            if current != last_streamed:
                try:
                    write_output_to_convex(current, status="processing")
                    last_streamed = current
                except Exception:
                    pass  # best effort streaming
        else:
            if stable_since and (time.time() - stable_since) >= STABLE_SECONDS:
                print("[bridge] Claude finished responding.", flush=True)
                return current
        time.sleep(POLL_INTERVAL)


def inject_input(text: str):
    """Inject input into Claude via tmux. Supports !!keys: protocol for TUI keystrokes."""
    print(f"[bridge] Injecting input: {repr(text)}", flush=True)

    if text.startswith("!!keys:"):
        # Parse key sequence: "!!keys:Up,Down,Enter" → individual keystrokes
        keys = text[7:].split(",")
        for key in keys:
            key = key.strip()
            if not key:
                continue
            subprocess.run(
                ["tmux", "send-keys", "-t", TMUX_PANE, key],
                check=True
            )
            print(f"[bridge] Key sent: {key}", flush=True)
            time.sleep(0.05)
    else:
        # Regular text input
        tmux_send(text)
        time.sleep(0.05)
        tmux_enter()


def write_output_to_convex(output: str, status: str = "idle"):
    """Write Claude's output to Convex."""
    global _last_good_output
    if output:
        _last_good_output = output
    bridge.mutation("terminalSessions:upsert", {
        "session_id": SESSION_ID,
        "output": output,
        "pending_input": "",
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    print(f"[bridge] Output written to Convex ({len(output)} chars, status={status}).", flush=True)


def set_status(status: str):
    """Update only the status in Convex, preserving the last known good output."""
    global _last_good_output
    try:
        captured = tmux_capture()
        if captured:
            _last_good_output = captured
    except Exception:
        captured = ""
    bridge.mutation("terminalSessions:upsert", {
        "session_id": SESSION_ID,
        "output": captured or _last_good_output,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    print(f"[bridge] Status updated: {status}", flush=True)


# ── Background screen monitor ─────────────────────────────────────────────────

_screen_monitor_paused = False  # Paused during active input processing

def screen_monitor_loop():
    """
    Continuously polls tmux screen and pushes changes to Convex.
    Runs independently of input/output cycles so the dashboard stays
    up-to-date even when Claude shows follow-up questions or TUI prompts.
    """
    last_sent = ""
    while True:
        if not _screen_monitor_paused:
            try:
                current = tmux_capture()
                if current and current != last_sent:
                    write_output_to_convex(current, status="idle")
                    last_sent = current
            except Exception:
                pass  # best effort
        time.sleep(POLL_INTERVAL * 5)  # 0.5s — light background polling


# ── Subscription thread ────────────────────────────────────────────────────────

def subscription_loop():
    """
    Runs in a separate thread.
    Uses ConvexBridge.subscribe() — blocking iterator via Convex SDK WebSocket.
    Receives INSTANT notification when pendingInput changes in Convex.
    No polling — purely event-driven.
    """
    print("[subscription] Starting subscription on terminalSessions:get...", flush=True)
    last_input = ""

    for snapshot in bridge.subscribe("terminalSessions:get", {"session_id": SESSION_ID}):
        if snapshot is None:
            continue

        pending = snapshot.get("pending_input", "") or ""

        # Skip if empty or same as last processed
        if not pending or pending == last_input:
            continue

        print(f"[subscription] New input detected via Convex: {repr(pending)}", flush=True)

        global _screen_monitor_paused

        if pending.startswith("!!keys:"):
            # Keystroke: fire-and-forget, no wait, no deduplication
            _screen_monitor_paused = True
            try:
                inject_input(pending)
                time.sleep(0.1)
                output = tmux_capture()
                write_output_to_convex(output, status="idle")
            except Exception as e:
                print(f"[subscription] Error sending key: {e}", flush=True)
            finally:
                _screen_monitor_paused = False
            last_input = ""  # allow repeating the same key
        else:
            # Normal text: full cycle with wait
            last_input = pending
            _screen_monitor_paused = True
            try:
                set_status("processing")
                inject_input(pending)
                output = wait_for_claude_response()
                write_output_to_convex(output, status="idle")
                print("[subscription] Cycle complete. Waiting for next input...\n", flush=True)
            except Exception as e:
                print(f"[subscription] Error in cycle: {e}", flush=True)
                try:
                    set_status("error")
                except Exception:
                    print("[subscription] Failed to set error status in Convex", flush=True)
            finally:
                _screen_monitor_paused = False


# ── Initial setup ──────────────────────────────────────────────────────────────

def setup_tmux_and_claude():
    """Create tmux session, open Claude, and bypass the welcome screen."""
    print("[setup] Creating tmux session...", flush=True)

    # Kill any existing sessions
    subprocess.run(["tmux", "kill-session", "-t", TMUX_SESSION], capture_output=True)
    subprocess.run(["tmux", "kill-server"], capture_output=True)
    time.sleep(0.3)

    # Create new detached session
    subprocess.run(["tmux", "new-session", "-d", "-s", TMUX_SESSION], check=True)
    time.sleep(0.5)

    # Open Claude
    print("[setup] Opening Claude Code...", flush=True)
    tmux_send("claude")
    tmux_enter()
    time.sleep(4)

    # Bypass welcome screen (Enter confirms default)
    print("[setup] Bypassing initial screen...", flush=True)
    tmux_enter()
    time.sleep(2)

    # Register initial state in Convex
    initial_output = tmux_capture()
    write_output_to_convex(initial_output, status="idle")
    print("[setup] Initial state registered in Convex.", flush=True)
    print("[setup] Claude ready. Bridge waiting for inputs via Convex.\n", flush=True)


# ── Terminal registration ──────────────────────────────────────────────────────

def register_terminal():
    """Register this terminal session in Convex after setup."""
    print(f"[setup] Registering terminal '{AGENT_NAME}' in Convex...", flush=True)
    bridge.mutation("terminalSessions:registerTerminal", {
        "session_id": SESSION_ID,
        "agent_name": AGENT_NAME,
        "display_name": DISPLAY_NAME,
        "ip_address": get_local_ip(),
    })
    print(f"[setup] Terminal registered (session={SESSION_ID}, agent={AGENT_NAME}).", flush=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def cleanup_and_exit(signum=None, frame=None):
    """Kill the tmux session, notify Convex, and exit the process."""
    print("\n[bridge] Shutting down tmux session...", flush=True)
    try:
        bridge.mutation("terminalSessions:disconnectTerminal", {
            "agent_name": AGENT_NAME,
        })
    except Exception:
        pass  # best effort on shutdown
    subprocess.run(["tmux", "kill-session", "-t", TMUX_SESSION], capture_output=True)
    print("[bridge] tmux session killed. Bye!", flush=True)
    os._exit(0)


if __name__ == "__main__":
    args = parse_args()

    # Populate globals from parsed args
    SESSION_ID = args.session_id
    DISPLAY_NAME = args.display_name
    TMUX_SESSION = args.tmux_session
    TMUX_PANE = f"{TMUX_SESSION}:0"
    AGENT_NAME = f"remote-{SESSION_ID[:8]}"

    # Initialize bridge with optional admin key
    bridge = ConvexBridge(args.convex_url, admin_key=args.admin_key)

    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    setup_tmux_and_claude()
    register_terminal()

    # Background screen monitor (catches changes between input cycles)
    monitor = threading.Thread(target=screen_monitor_loop, daemon=True)
    monitor.start()

    # Subscription runs in daemon thread
    t = threading.Thread(target=subscription_loop, daemon=True)
    t.start()

    print("=" * 60)
    print(f"Bridge active — session={SESSION_ID}, agent={AGENT_NAME}")
    print(f"Display name: {DISPLAY_NAME} | tmux: {TMUX_SESSION}")
    print("Ctrl+C to stop.")
    print("=" * 60 + "\n")

    while True:
        time.sleep(1)

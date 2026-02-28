#!/usr/bin/env python3
"""
Terminal Bridge — Production-ready bridge between Convex and a local tmux/Claude session.

Architecture:
  [Convex DB] <--poll/mutation--> [Bridge] <--send-keys/capture--> [tmux/Claude]

Two polling loops run as daemon threads:
  - input_poll_loop: polls Convex for pendingInput every 300ms
  - screen_monitor_loop: polls tmux screen every 300ms and pushes changes to Convex

Note: We use polling instead of ConvexBridge.subscribe() because the Convex Python
SDK's Rust/Tokio backend captures SIGINT at the OS level, making Ctrl+C non-functional.
"""

from __future__ import annotations

import argparse
import atexit
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


# ── TerminalBridge class ───────────────────────────────────────────────────────

class TerminalBridge:
    """Encapsulates all state and logic for the terminal bridge."""

    def __init__(
        self,
        session_id: str,
        display_name: str,
        convex_url: str,
        admin_key: str | None,
        tmux_session: str,
    ) -> None:
        self.session_id = session_id
        self.display_name = display_name
        self.tmux_session = tmux_session
        self.tmux_pane = f"{tmux_session}:0"
        self.agent_name = f"remote-{session_id[:8]}"

        # Two separate ConvexBridge instances for thread safety:
        # - bridge: used by the input poll loop thread
        # - monitor_bridge: used by the screen monitor thread and cleanup
        self.bridge = ConvexBridge(convex_url, admin_key=admin_key)
        self.monitor_bridge = ConvexBridge(convex_url, admin_key=admin_key)

        self._last_good_output: str = ""
        self._screen_monitor_paused: bool = False
        self._cleaned_up: bool = False  # guard against double-cleanup

    # ── tmux operations ────────────────────────────────────────────────────────

    def tmux_send(self, text: str) -> None:
        """Send text to the tmux pane."""
        subprocess.run(["tmux", "send-keys", "-t", self.tmux_pane, text, ""], check=True)

    def tmux_enter(self) -> None:
        """Send Enter to the tmux pane."""
        subprocess.run(["tmux", "send-keys", "-t", self.tmux_pane, "", "Enter"], check=True)

    def tmux_capture(self) -> str:
        """Capture the current content of the tmux pane."""
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", self.tmux_pane, "-p", "-S", "-50"],
            capture_output=True, text=True
        )
        return result.stdout.strip()

    def inject_input(self, text: str) -> None:
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
                    ["tmux", "send-keys", "-t", self.tmux_pane, key],
                    check=True
                )
                print(f"[bridge] Key sent: {key}", flush=True)
                time.sleep(0.05)
        else:
            # Regular text input
            self.tmux_send(text)
            time.sleep(0.05)
            self.tmux_enter()

    def wait_for_claude_response(self) -> str:
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
            current = self.tmux_capture()
            if current != last_output:
                last_output = current
                stable_since = time.time()
                # Stream intermediate output to Convex for real-time dashboard updates
                if current != last_streamed:
                    try:
                        self.write_output_to_convex(current, status="processing")
                        last_streamed = current
                    except Exception:
                        pass  # best effort streaming
            else:
                if stable_since and (time.time() - stable_since) >= STABLE_SECONDS:
                    print("[bridge] Claude finished responding.", flush=True)
                    return current
            time.sleep(POLL_INTERVAL)

    # ── Convex operations ──────────────────────────────────────────────────────

    def write_output_to_convex(self, output: str, status: str = "idle") -> None:
        """Write Claude's output to Convex."""
        if output:
            self._last_good_output = output
        self.bridge.mutation("terminalSessions:upsert", {
            "session_id": self.session_id,
            "output": output,
            "pending_input": "",
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"[bridge] Output written to Convex ({len(output)} chars, status={status}).", flush=True)

    def set_status(self, status: str) -> None:
        """Update only the status in Convex, preserving the last known good output."""
        try:
            captured = self.tmux_capture()
            if captured:
                self._last_good_output = captured
        except Exception:
            captured = ""
        self.bridge.mutation("terminalSessions:upsert", {
            "session_id": self.session_id,
            "output": captured or self._last_good_output,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"[bridge] Status updated: {status}", flush=True)

    def update_screen_only(self, output: str) -> None:
        """Lightweight output-only update for the background monitor.

        Uses monitor_bridge (separate ConvexClient) for thread safety.
        Does NOT touch pending_input to avoid interfering with subscription loop.
        """
        self.monitor_bridge.mutation("terminalSessions:upsert", {
            "session_id": self.session_id,
            "output": output,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "idle",
        })

    # ── Lifecycle management ───────────────────────────────────────────────────

    def setup_tmux_and_claude(self) -> None:
        """Create tmux session, open Claude, and bypass the welcome screen."""
        print("[setup] Creating tmux session...", flush=True)

        # Kill any existing session with the same name (does NOT affect other sessions)
        subprocess.run(["tmux", "kill-session", "-t", self.tmux_session], capture_output=True)
        time.sleep(0.3)

        # Create new detached session
        subprocess.run(["tmux", "new-session", "-d", "-s", self.tmux_session], check=True)
        time.sleep(0.5)

        # Open Claude
        print("[setup] Opening Claude Code...", flush=True)
        self.tmux_send("claude")
        self.tmux_enter()
        time.sleep(4)

        # Bypass welcome screen (Enter confirms default)
        print("[setup] Bypassing initial screen...", flush=True)
        self.tmux_enter()
        time.sleep(2)

        # Register initial state in Convex
        initial_output = self.tmux_capture()
        self.write_output_to_convex(initial_output, status="idle")
        print("[setup] Initial state registered in Convex.", flush=True)
        print("[setup] Claude ready. Bridge waiting for inputs via Convex.\n", flush=True)

    def register_terminal(self) -> None:
        """Register this terminal session in Convex after setup."""
        print(f"[setup] Registering terminal '{self.agent_name}' in Convex...", flush=True)
        self.bridge.mutation("terminalSessions:registerTerminal", {
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "display_name": self.display_name,
            "ip_address": get_local_ip(),
        })
        print(f"[setup] Terminal registered (session={self.session_id}, agent={self.agent_name}).", flush=True)

    def cleanup(self, signum=None, frame=None) -> None:
        """Kill the tmux session, notify Convex, and exit the process.

        If called a second time (e.g., repeated Ctrl+C), force-exits immediately.
        """
        if self._cleaned_up:
            # Second signal: force exit NOW
            print("\n[bridge] Force exit.", flush=True)
            os._exit(1)
        self._cleaned_up = True

        print("\n[bridge] Shutting down...", flush=True)

        # 1. Kill tmux FIRST (local, always fast)
        subprocess.run(["tmux", "kill-session", "-t", self.tmux_session], capture_output=True)
        print("[bridge] tmux killed.", flush=True)

        # 2. Notify Convex in a daemon thread with timeout
        def _notify():
            try:
                self.monitor_bridge.mutation("terminalSessions:disconnectTerminal", {
                    "agent_name": self.agent_name,
                })
                print("[bridge] Convex notified.", flush=True)
            except Exception:
                pass

        t = threading.Thread(target=_notify, daemon=True)
        t.start()
        t.join(timeout=3)

        print("[bridge] Bye!", flush=True)
        os._exit(0)

    # ── Background threads ─────────────────────────────────────────────────────

    def screen_monitor_loop(self) -> None:
        """
        Continuously polls tmux screen and pushes changes to Convex.
        Uses its own ConvexBridge instance for thread safety.
        Runs independently of input/output cycles so the dashboard stays
        up-to-date even when Claude shows follow-up questions or TUI prompts.
        """
        last_sent = ""
        while True:
            if not self._screen_monitor_paused:
                try:
                    current = self.tmux_capture()
                    if current and current != last_sent:
                        print(f"[monitor] Screen changed ({len(current)} chars), pushing...", flush=True)
                        self.update_screen_only(current)
                        last_sent = current
                except Exception as e:
                    print(f"[monitor] Error: {e}", flush=True)
            time.sleep(0.3)  # 300ms polling

    def input_poll_loop(self) -> None:
        """
        Polls Convex for new pendingInput every 300ms.

        We use polling instead of ConvexBridge.subscribe() because the Convex
        Python SDK's Rust/Tokio backend captures SIGINT at the OS level, making
        Ctrl+C and all signal handlers non-functional while a subscription is active.
        300ms polling is imperceptible for human-typed input.
        """
        print("[input] Polling for pendingInput...", flush=True)
        last_input = ""

        while True:
            try:
                snapshot = self.bridge.query("terminalSessions:get", {"session_id": self.session_id})
            except Exception as e:
                print(f"[input] Poll error: {e}", flush=True)
                time.sleep(1)
                continue

            if snapshot is None:
                time.sleep(0.3)
                continue

            pending = snapshot.get("pending_input", "") or ""

            # Skip if empty or same as last processed
            if not pending or pending == last_input:
                time.sleep(0.3)
                continue

            print(f"[input] New input detected: {repr(pending)}", flush=True)

            if pending.startswith("!!keys:"):
                # Keystroke: fire-and-forget, no wait, no deduplication
                self._screen_monitor_paused = True
                try:
                    self.inject_input(pending)
                    time.sleep(0.1)
                    output = self.tmux_capture()
                    self.write_output_to_convex(output, status="idle")
                except Exception as e:
                    print(f"[input] Error sending key: {e}", flush=True)
                finally:
                    self._screen_monitor_paused = False
                last_input = ""  # allow repeating the same key
            else:
                # Normal text: full cycle with wait
                last_input = pending
                self._screen_monitor_paused = True
                try:
                    self.set_status("processing")
                    self.inject_input(pending)
                    output = self.wait_for_claude_response()
                    self.write_output_to_convex(output, status="idle")
                    print("[input] Cycle complete. Post-response watch...", flush=True)

                    # Post-response watch: Claude Code may render a TUI question
                    # widget AFTER the main response stabilizes. Poll for 5s to
                    # catch any late screen changes (same thread/bridge = reliable).
                    for i in range(25):  # 25 × 200ms = 5s max
                        time.sleep(0.2)
                        try:
                            fresh = self.tmux_capture()
                            if fresh and fresh != output:
                                self.write_output_to_convex(fresh, status="idle")
                                print(f"[input] Post-response update #{i+1} ({len(fresh)} chars)", flush=True)
                                output = fresh
                        except Exception:
                            pass

                    print("[input] Waiting for next input...\n", flush=True)
                except Exception as e:
                    print(f"[input] Error in cycle: {e}", flush=True)
                    try:
                        self.set_status("error")
                    except Exception:
                        print("[input] Failed to set error status in Convex", flush=True)
                finally:
                    self._screen_monitor_paused = False

    # ── Entry point ────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Set up signal handlers, register atexit, start threads, and enter main loop."""
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        # SIGHUP: sent when the controlling terminal is closed
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self.cleanup)

        # atexit fallback: catches unhandled exceptions and other non-signal exits
        atexit.register(self.cleanup)

        self.setup_tmux_and_claude()
        self.register_terminal()

        # Background screen monitor (catches changes between input cycles)
        monitor = threading.Thread(target=self.screen_monitor_loop, daemon=True)
        monitor.start()

        # Input polling runs in daemon thread
        t = threading.Thread(target=self.input_poll_loop, daemon=True)
        t.start()

        print("=" * 60)
        print(f"Bridge active — session={self.session_id}, agent={self.agent_name}")
        print(f"Display name: {self.display_name} | tmux: {self.tmux_session}")
        print("Ctrl+C to stop.")
        print("=" * 60 + "\n")

        while True:
            time.sleep(1)


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()
    tb = TerminalBridge(
        session_id=args.session_id,
        display_name=args.display_name,
        convex_url=args.convex_url,
        admin_key=args.admin_key,
        tmux_session=args.tmux_session,
    )
    tb.run()

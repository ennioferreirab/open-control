"use client";

import { useEffect, useRef, useState } from "react";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";

async function copyToClipboard(text: string): Promise<void> {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    if (typeof document === "undefined") return;
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "true");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }
}

interface AgentTerminalProps {
  agentName: string;
  provider: string;
  prompt?: string;
  scopeId?: string;
  taskId?: string;
  /** When true, sends a terminate signal before closing so the backend kills the tmux session. */
  terminateOnClose?: boolean;
}

export function AgentTerminal({
  agentName,
  provider,
  prompt,
  scopeId,
  taskId,
  terminateOnClose,
}: AgentTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const statusRef = useRef<"connecting" | "connected" | "error">("connecting");
  const [status, setStatus] = useState<"connecting" | "connected" | "error">("connecting");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    statusRef.current = "connecting";

    const terminal = new Terminal({
      cursorBlink: true,
      fontFamily: '"SFMono-Regular", "Menlo", "Monaco", monospace',
      fontSize: 15,
      lineHeight: 1.25,
      scrollback: 10000,
      theme: {
        background: "#09090b",
        foreground: "#f4f4f5",
        cursor: "#f4f4f5",
        selectionBackground: "#27272a",
      },
    });
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);

    const container = containerRef.current;
    if (!container) {
      terminal.dispose();
      fitAddon.dispose();
      return undefined;
    }

    terminal.open(container);
    fitAddon.fit();

    // --- Clipboard / selection support ---
    // Without tmux mouse mode, xterm.js handles text selection natively.
    // Intercept Cmd+C / Ctrl+C when there is a selection so it copies
    // instead of sending ^C to the process.
    terminal.attachCustomKeyEventHandler((event) => {
      const isCopy =
        (event.ctrlKey || event.metaKey) &&
        !event.altKey &&
        event.key.toLowerCase() === "c" &&
        terminal.hasSelection();
      if (!isCopy) return true;
      void copyToClipboard(terminal.getSelection());
      event.preventDefault();
      return false;
    });

    // Document-level copy event handler so right-click → Copy also works.
    const handleDocCopy = (event: ClipboardEvent) => {
      if (!terminal.hasSelection()) return;
      event.clipboardData?.setData("text/plain", terminal.getSelection());
      event.preventDefault();
    };
    document.addEventListener("copy", handleDocCopy);

    const resolvedScopeId = scopeId ?? `create:${agentName}`;

    const params = new URLSearchParams({
      provider,
      agentName,
      scopeKind: "chat",
      scopeId: resolvedScopeId,
      surface: "chat",
      columns: String(terminal.cols),
      rows: String(terminal.rows),
    });
    if (taskId) {
      params.set("taskId", taskId);
    }
    if (prompt) {
      params.set("prompt", prompt);
    }
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsPort = process.env.NEXT_PUBLIC_INTERACTIVE_PORT || "8765";
    const url = `${protocol}://${window.location.hostname}:${wsPort}/interactive?${params}`;
    const socket = new WebSocket(url);
    socket.binaryType = "arraybuffer";

    socket.onopen = () => {
      statusRef.current = "connecting";
      setStatus("connecting");
      setError(null);
    };

    socket.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          const payload = JSON.parse(event.data) as { type?: string; message?: string };
          if (payload.type === "attached") {
            statusRef.current = "connected";
            setStatus("connected");
            setError(null);
            return;
          }
          if (payload.type === "error") {
            const message = payload.message || "Interactive terminal connection failed.";
            statusRef.current = "error";
            setStatus("error");
            setError(message);
            return;
          }
        } catch {
          // Not a control message; fall through to terminal output.
        }
        terminal.write(event.data);
      } else {
        terminal.write(new Uint8Array(event.data as ArrayBuffer));
      }
    };

    socket.onerror = () => {
      statusRef.current = "error";
      setStatus("error");
      setError("Interactive terminal connection failed.");
    };

    socket.onclose = () => {
      if (statusRef.current === "connected") {
        return;
      }
      statusRef.current = "error";
      setStatus("error");
      setError((existing) => existing ?? "Interactive terminal connection closed before attach.");
    };

    const inputSubscription = terminal.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "input", data }));
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(
          JSON.stringify({
            type: "resize",
            columns: terminal.cols,
            rows: terminal.rows,
          }),
        );
      }
    });
    resizeObserver.observe(container);

    return () => {
      if (terminateOnClose && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "terminate" }));
      }
      socket.close();
      inputSubscription.dispose();
      document.removeEventListener("copy", handleDocCopy);
      resizeObserver.disconnect();
      terminal.dispose();
      fitAddon.dispose();
    };
  }, [agentName, provider, prompt, scopeId, taskId, terminateOnClose]);

  return (
    <div className="relative h-full w-full bg-zinc-950">
      {status === "connecting" && (
        <div className="absolute left-3 top-3 z-10 rounded bg-zinc-900/90 px-2 py-1 text-xs text-zinc-200">
          Connecting terminal...
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="absolute left-3 right-3 top-12 z-10 rounded border border-red-500/40 bg-red-950/85 px-3 py-2 text-xs text-red-100"
        >
          {error}
        </div>
      )}
      <div
        ref={containerRef}
        data-testid="agent-terminal-container"
        className="h-full w-full overflow-hidden"
      />
    </div>
  );
}

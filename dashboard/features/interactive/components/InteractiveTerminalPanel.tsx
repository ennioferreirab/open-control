"use client";

import { useEffect, useRef, useState } from "react";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";

import { cn } from "@/lib/utils";

type TerminalStatus = "connecting" | "connected" | "reconnecting" | "error";

const STATUS_LABELS: Record<TerminalStatus, string> = {
  connecting: "Connecting",
  connected: "Connected",
  reconnecting: "Reconnecting",
  error: "Error",
};

interface InteractiveTerminalPanelProps {
  agentName: string;
  provider: string;
  scopeKind?: "chat" | "task";
  scopeId?: string;
  surface?: string;
  taskId?: string;
}

export function InteractiveTerminalPanel({
  agentName,
  provider,
  scopeKind = "chat",
  scopeId,
  surface = scopeKind === "task" ? "step" : "chat",
  taskId,
}: InteractiveTerminalPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const attachTokenRef = useRef<string | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const mountedRef = useRef(true);
  const [status, setStatus] = useState<TerminalStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    const terminal = new Terminal({
      cursorBlink: true,
      fontFamily: '"SFMono-Regular", "Menlo", "Monaco", monospace',
      fontSize: 12,
      lineHeight: 1.25,
      theme: {
        background: "#09090b",
        foreground: "#f4f4f5",
        cursor: "#f4f4f5",
        selectionBackground: "#27272a",
      },
    });
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminalRef.current = terminal;
    fitAddonRef.current = fitAddon;

    const container = containerRef.current;
    if (!container) {
      return undefined;
    }

    terminal.open(container);
    fitAddon.fit();

    const sendResize = () => {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN || !terminalRef.current) {
        return;
      }
      socket.send(
        JSON.stringify({
          type: "resize",
          columns: terminalRef.current.cols,
          rows: terminalRef.current.rows,
        }),
      );
    };

    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
      sendResize();
    });
    resizeObserver.observe(container);

    const inputSubscription = terminal.onData((data) => {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        return;
      }
      socket.send(JSON.stringify({ type: "input", data }));
    });

    const connect = () => {
      if (!mountedRef.current || !terminalRef.current) {
        return;
      }

      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const resolvedScopeId =
        scopeId ?? (scopeKind === "task" ? (taskId ?? `task:${agentName}`) : `chat:${agentName}`);
      const resolvedTaskId =
        taskId ?? (scopeKind === "task" ? resolvedScopeId : `chat-${agentName}`);
      const params = new URLSearchParams({
        provider,
        agentName,
        scopeKind,
        scopeId: resolvedScopeId,
        surface,
        taskId: resolvedTaskId,
        columns: String(terminalRef.current.cols || 120),
        rows: String(terminalRef.current.rows || 40),
      });
      if (sessionIdRef.current) {
        params.set("sessionId", sessionIdRef.current);
        if (attachTokenRef.current) {
          params.set("attachToken", attachTokenRef.current);
        }
      }

      const nextSocket = new WebSocket(
        `${protocol}://${window.location.hostname}:8765/interactive?${params.toString()}`,
      );
      nextSocket.binaryType = "arraybuffer";
      socketRef.current = nextSocket;

      nextSocket.onopen = () => {
        if (!mountedRef.current || socketRef.current !== nextSocket) {
          return;
        }
        reconnectAttemptsRef.current = 0;
        setStatus("connected");
        setError(null);
      };

      nextSocket.onmessage = (event) => {
        if (!terminalRef.current || socketRef.current !== nextSocket) {
          return;
        }

        if (typeof event.data === "string") {
          try {
            const payload = JSON.parse(event.data) as {
              type?: string;
              message?: string;
              sessionId?: string;
              attachToken?: string;
            };
            if (payload.type === "attached") {
              sessionIdRef.current = payload.sessionId ?? null;
              attachTokenRef.current = payload.attachToken ?? null;
              setSessionId(payload.sessionId ?? null);
              return;
            }
            if (payload.type === "error") {
              setStatus("error");
              setError(payload.message ?? "Interactive runtime error");
              terminalRef.current.writeln(
                `\r\n[error] ${payload.message ?? "Interactive runtime error"}`,
              );
              return;
            }
          } catch {
            terminalRef.current.write(event.data);
            return;
          }

          terminalRef.current.write(event.data);
          return;
        }

        terminalRef.current.write(new Uint8Array(event.data));
      };

      nextSocket.onerror = () => {
        if (!mountedRef.current || socketRef.current !== nextSocket) {
          return;
        }
        setStatus("error");
        setError("Interactive terminal connection failed.");
      };

      nextSocket.onclose = () => {
        if (!mountedRef.current || socketRef.current !== nextSocket) {
          return;
        }
        socketRef.current = null;
        const nextAttempt = reconnectAttemptsRef.current + 1;
        reconnectAttemptsRef.current = nextAttempt;
        setStatus("reconnecting");
        const delayMs = Math.min(1000 * nextAttempt, 4000);
        reconnectTimerRef.current = window.setTimeout(connect, delayMs);
      };
    };

    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      const activeSocket = socketRef.current;
      socketRef.current = null;
      activeSocket?.close();
      inputSubscription.dispose();
      resizeObserver.disconnect();
      terminal.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
  }, [agentName, provider, scopeId, scopeKind, surface, taskId]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-zinc-950 text-zinc-100">
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-400">
            Native TUI
          </span>
          <span className="text-xs text-zinc-500">@{agentName}</span>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span
            className={cn(
              "rounded-full px-2 py-0.5 font-medium",
              status === "connected"
                ? "bg-emerald-500/10 text-emerald-300"
                : status === "error"
                  ? "bg-red-500/10 text-red-300"
                  : "bg-zinc-800 text-zinc-300",
            )}
          >
            {STATUS_LABELS[status]}
          </span>
          {sessionId && (
            <span className="rounded-full bg-zinc-900 px-2 py-0.5 text-zinc-500">
              {sessionId.slice(0, 16)}
            </span>
          )}
        </div>
      </div>
      {error && (
        <div
          role="alert"
          className="border-b border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-200"
        >
          {error}
        </div>
      )}
      <div
        ref={containerRef}
        data-testid="interactive-terminal"
        className="min-h-0 flex-1 overflow-hidden px-2 py-2"
      />
    </div>
  );
}

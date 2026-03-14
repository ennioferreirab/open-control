"use client";

import { useEffect, useRef } from "react";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";

interface AgentTerminalProps {
  agentName: string;
  provider: string;
  prompt?: string;
  scopeId?: string;
}

export function AgentTerminal({ agentName, provider, prompt, scopeId }: AgentTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
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

    const container = containerRef.current;
    if (!container) {
      terminal.dispose();
      fitAddon.dispose();
      return undefined;
    }

    terminal.open(container);
    fitAddon.fit();

    const resolvedScopeId = scopeId ?? `create:${agentName}`;

    const params = new URLSearchParams({
      provider,
      agentName,
      scopeKind: "chat",
      scopeId: resolvedScopeId,
      surface: "chat",
      taskId: resolvedScopeId,
      columns: String(terminal.cols),
      rows: String(terminal.rows),
    });
    if (prompt) {
      params.set("prompt", prompt);
    }
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.hostname}:8765/interactive?${params}`;
    const socket = new WebSocket(url);
    socket.binaryType = "arraybuffer";

    socket.onmessage = (event) => {
      if (typeof event.data === "string") {
        terminal.write(event.data);
      } else {
        terminal.write(new Uint8Array(event.data as ArrayBuffer));
      }
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
      socket.close();
      inputSubscription.dispose();
      resizeObserver.disconnect();
      terminal.dispose();
      fitAddon.dispose();
    };
  }, [agentName, provider, prompt, scopeId]);

  return (
    <div
      ref={containerRef}
      data-testid="agent-terminal-container"
      className="h-full w-full overflow-hidden bg-zinc-950"
    />
  );
}

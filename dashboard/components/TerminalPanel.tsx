"use client";
import { useEffect, useRef, useState } from "react";
import { Pencil } from "lucide-react";
import { useTerminalPanelState } from "@/features/terminal/hooks/useTerminalPanelState";

interface TerminalPanelProps {
  sessionId: string;
  agentName?: string;
  ipAddress?: string;
}

export function TerminalPanel({ sessionId, agentName, ipAddress }: TerminalPanelProps) {
  const [input, setInput] = useState("");
  const outputContainerRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const { session, displayName, send, wake, rename } = useTerminalPanelState(sessionId, agentName);

  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");

  useEffect(() => {
    if (session?.output && isAtBottom) {
      requestAnimationFrame(() => {
        const outputContainer = outputContainerRef.current;
        if (!outputContainer) return;
        outputContainer.scrollTop = Math.max(
          0,
          outputContainer.scrollHeight - outputContainer.clientHeight,
        );
      });
    }
  }, [session?.output, isAtBottom]);

  const [error, setError] = useState<string | null>(null);

  const handleOutputScroll = () => {
    const outputContainer = outputContainerRef.current;
    if (!outputContainer) return;

    const distanceFromBottom =
      outputContainer.scrollHeight -
      outputContainer.clientHeight -
      outputContainer.scrollTop;

    setIsAtBottom(distanceFromBottom <= 8);
  };

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    setError(null);
    send(trimmed).catch((e) => {
      setError(e instanceof Error ? e.message : "Failed to send input");
    });
    setInput("");
  };

  const isProcessing = session?.status === "processing";

  const startEditing = () => {
    setEditValue(displayName);
    setIsEditing(true);
    // Focus the input on next render
    setTimeout(() => renameInputRef.current?.focus(), 0);
  };

  const commitEdit = () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== displayName && agentName) {
      rename(trimmed).catch(() => {});
    }
    setIsEditing(false);
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setEditValue("");
  };

  // Determine status badge appearance
  let dotColor: string;
  let statusText: string;

  const isSleeping = session?.sleepMode === true;

  if (session === undefined) {
    dotColor = "bg-zinc-500";
    statusText = "Loading...";
  } else if (session === null) {
    dotColor = "bg-zinc-500";
    statusText = "Disconnected";
  } else if (isSleeping) {
    dotColor = "bg-blue-400 animate-pulse";
    statusText = "Sleeping";
  } else if (session.status === "processing") {
    dotColor = "bg-amber-400 animate-pulse";
    statusText = "Processing...";
  } else if (session.status === "error") {
    dotColor = "bg-red-500";
    statusText = "Error";
  } else {
    dotColor = "bg-green-500";
    statusText = "Idle";
  }

  return (
    <div className="flex h-full flex-col bg-zinc-950">
      {/* Status badge */}
      <div className="flex items-center px-3 py-2 border-b border-zinc-800 gap-2">
        <span className={`h-2 w-2 rounded-full ${dotColor}`} />
        <span className="text-xs text-zinc-400">{statusText}</span>
        {isSleeping && (
          <button
            type="button"
            onClick={() => wake().catch(() => {})}
            className="rounded bg-zinc-700 px-2 py-0.5 text-xs text-zinc-300 hover:bg-zinc-600 active:bg-zinc-500"
          >
            Wake
          </button>
        )}
      </div>

      {/* Terminal header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-zinc-800 bg-zinc-900">
        <div className="flex items-center gap-2">
          {isEditing ? (
            <input
              ref={renameInputRef}
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  commitEdit();
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  cancelEdit();
                }
              }}
              className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs font-medium text-zinc-100 outline-none focus:ring-1 focus:ring-zinc-500 w-40"
            />
          ) : (
            <div className="flex items-center gap-1 group">
              <span className="text-xs font-medium text-zinc-300">{displayName}</span>
              {agentName && (
                <button
                  type="button"
                  onClick={startEditing}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-zinc-700 text-zinc-500 hover:text-zinc-300"
                  title="Rename agent"
                >
                  <Pencil size={10} />
                </button>
              )}
            </div>
          )}
          {ipAddress && (
            <span className="text-[10px] font-mono text-zinc-500">{ipAddress}</span>
          )}
        </div>
      </div>

      {/* Output display */}
      <div
        ref={outputContainerRef}
        data-testid="terminal-output"
        onScroll={handleOutputScroll}
        className="flex-1 overflow-y-auto bg-zinc-950 p-3"
      >
        <pre className="whitespace-pre-wrap break-words font-mono text-xs text-green-400">{session?.output || "Waiting for bridge connection..."}</pre>
        {error && (
          <p className="mt-2 text-xs text-red-400">{error}</p>
        )}
      </div>

      {/* TUI Navigation */}
      <div className="flex items-center gap-1 border-t border-zinc-800 bg-zinc-900 px-2 py-1">
        <span className="text-[10px] text-zinc-500 mr-1">TUI</span>
        {[
          { label: "↑", key: "Up" },
          { label: "↓", key: "Down" },
          { label: "←", key: "Left" },
          { label: "→", key: "Right" },
          { label: "Enter", key: "Enter" },
          { label: "Tab", key: "Tab" },
          { label: "Space", key: "Space" },
          { label: "Esc", key: "Escape" },
          { label: "Ctrl+c", key: "C-c" },
        ].map(({ label, key }) => (
          <button
            key={key}
            type="button"
            onClick={() => {
              send(`!!keys:${key}`).catch(() => {});
            }}
            className="rounded bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-300 hover:bg-zinc-700 active:bg-zinc-600"
          >
            {label}
          </button>
        ))}
      </div>

      {/* Input bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="flex gap-2 border-t border-zinc-800 bg-zinc-900 p-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isProcessing ? "Processing..." : "Send a message..."}
          disabled={isProcessing}
          className="flex-1 rounded bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isProcessing || !input.trim()}
          className="rounded bg-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </div>
  );
}

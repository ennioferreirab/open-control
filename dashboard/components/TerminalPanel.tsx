"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";

export function TerminalPanel() {
  const [input, setInput] = useState("");
  const outputEndRef = useRef<HTMLDivElement>(null);

  const session = useQuery(api.terminalSessions.get, { sessionId: "poc-bridge-001" });
  const sendInput = useMutation(api.terminalSessions.sendInput);

  useEffect(() => {
    if (session?.output) {
      requestAnimationFrame(() => {
        outputEndRef.current?.scrollIntoView({ behavior: "smooth" });
      });
    }
  }, [session?.output]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    sendInput({ sessionId: "poc-bridge-001", input: trimmed });
    setInput("");
  };

  const isProcessing = session?.status === "processing";

  // Determine status badge appearance
  let dotColor: string;
  let statusText: string;

  if (session === undefined) {
    dotColor = "bg-zinc-500";
    statusText = "Disconnected";
  } else if (session === null) {
    dotColor = "bg-zinc-500";
    statusText = "Disconnected";
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
      <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-800">
        <span className={`h-2 w-2 rounded-full ${dotColor}`} />
        <span className="text-xs text-zinc-400">{statusText}</span>
      </div>

      {/* Output display */}
      <div className="flex-1 overflow-y-auto bg-zinc-950 p-3">
        <pre className="whitespace-pre-wrap break-words font-mono text-xs text-green-400">
          {session?.output || "Waiting for bridge connection..."}
        </pre>
        <div ref={outputEndRef} />
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

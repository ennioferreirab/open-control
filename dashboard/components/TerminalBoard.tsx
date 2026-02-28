"use client";

import { lazy, Suspense } from "react";
import { X } from "lucide-react";
import { useBoard } from "./BoardContext";

const TerminalPanel = lazy(() =>
  import("@/components/TerminalPanel").then((mod) => ({ default: mod.TerminalPanel }))
);

export function TerminalBoard() {
  const { openTerminals, closeTerminal } = useBoard();

  return (
    <div className="flex h-full flex-col gap-px bg-zinc-800">
      {openTerminals.map(({ sessionId, agentName }) => (
        <div key={sessionId} className="relative flex-1 min-h-0">
          <Suspense fallback={<div className="flex-1 p-4 text-muted-foreground text-xs">Loading...</div>}>
            <TerminalPanel sessionId={sessionId} />
          </Suspense>
          <button
            onClick={() => closeTerminal(sessionId)}
            aria-label={`Close terminal for ${agentName}`}
            className="absolute top-2 right-2 z-10 rounded bg-zinc-800/80 p-1 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}

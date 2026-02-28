"use client";

import { lazy, Suspense } from "react";
import { X } from "lucide-react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { useBoard } from "./BoardContext";

const TerminalPanel = lazy(() =>
  import("@/components/TerminalPanel").then((mod) => ({ default: mod.TerminalPanel }))
);

function TerminalEntry({ sessionId, agentName, onClose }: { sessionId: string; agentName: string; onClose: () => void }) {
  const agents = useQuery(api.agents.list);
  const agent = agents?.find((a) => a.name === agentName);
  const ipAddress = agent?.variables?.find((v) => v.name === "ipAddress")?.value;

  return (
    <div className="relative flex-1 min-h-0">
      <Suspense fallback={<div className="flex-1 p-4 text-muted-foreground text-xs">Loading...</div>}>
        <TerminalPanel sessionId={sessionId} agentName={agent?.displayName || agentName} ipAddress={ipAddress} />
      </Suspense>
      <button
        onClick={onClose}
        aria-label={`Close terminal for ${agentName}`}
        className="absolute top-2 right-2 z-10 rounded bg-zinc-800/80 p-1 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function TerminalBoard() {
  const { openTerminals, closeTerminal } = useBoard();

  return (
    <div className="flex h-full flex-col gap-px bg-zinc-800">
      {openTerminals.map(({ sessionId, agentName }) => (
        <TerminalEntry
          key={sessionId}
          sessionId={sessionId}
          agentName={agentName}
          onClose={() => closeTerminal(sessionId)}
        />
      ))}
    </div>
  );
}

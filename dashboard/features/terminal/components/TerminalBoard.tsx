"use client";

import { lazy, Suspense } from "react";
import { X } from "lucide-react";
import { useTerminalBoard } from "@/features/terminal/hooks/useTerminalBoard";

const TerminalPanel = lazy(() =>
  import("@/components/TerminalPanel").then((mod) => ({ default: mod.TerminalPanel })),
);

function TerminalEntry({
  agentName,
  ipAddress,
  onClose,
  sessionId,
}: {
  agentName: string;
  ipAddress?: string;
  onClose: () => void;
  sessionId: string;
}) {
  return (
    <div className="relative flex-1 min-h-0">
      <Suspense fallback={<div className="flex-1 p-4 text-xs text-muted-foreground">Loading...</div>}>
        <TerminalPanel sessionId={sessionId} agentName={agentName} ipAddress={ipAddress} />
      </Suspense>
      <button
        onClick={onClose}
        aria-label={`Close terminal for ${agentName}`}
        className="absolute right-2 top-2 z-10 rounded bg-zinc-800/80 p-1 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function TerminalBoard() {
  const { closeTerminal, ipAddressByAgent, openTerminals } = useTerminalBoard();

  return (
    <div className="flex h-full flex-col gap-px bg-zinc-800">
      {openTerminals.map(({ agentName, sessionId }) => (
        <TerminalEntry
          key={sessionId}
          sessionId={sessionId}
          agentName={agentName}
          ipAddress={ipAddressByAgent.get(agentName)}
          onClose={() => closeTerminal(sessionId)}
        />
      ))}
    </div>
  );
}

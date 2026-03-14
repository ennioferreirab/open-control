"use client";

import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getInteractiveAgentProvider } from "@/features/interactive/hooks/useInteractiveAgentProvider";
import { AgentTerminal } from "./AgentTerminal";

interface AgentAuthoringWizardProps {
  open: boolean;
  onClose: () => void;
}

export function AgentAuthoringWizard({ open, onClose }: AgentAuthoringWizardProps) {
  const [scopeId] = useState(() => `create-agent:${crypto.randomUUID()}`);
  const nanobotAgent = useQuery(api.agents.getByName, { name: "nanobot" });
  const provider = getInteractiveAgentProvider(nanobotAgent) ?? "claude-code";

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-4xl p-0 h-[600px] flex flex-col">
        <DialogHeader className="border-b px-6 py-4">
          <DialogTitle className="text-lg font-semibold">Create Agent</DialogTitle>
          <DialogDescription className="sr-only">
            Interactive terminal session to design and publish a new agent.
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 min-h-0">
          {open && (
            <AgentTerminal
              agentName="nanobot"
              provider={provider}
              scopeId={scopeId}
              prompt="Use the create-agent skill to walk me through creating a new agent."
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

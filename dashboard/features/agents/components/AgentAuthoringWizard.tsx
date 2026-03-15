"use client";

import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { AgentTerminal } from "./AgentTerminal";
import { ProviderSelector, type WizardProvider } from "./ProviderSelector";

interface AgentAuthoringWizardProps {
  open: boolean;
  onClose: () => void;
}

export function AgentAuthoringWizard({ open, onClose }: AgentAuthoringWizardProps) {
  const [generation, setGeneration] = useState(0);
  const [provider, setProvider] = useState<WizardProvider>("claude-code");
  const scopeId = useMemo(() => `create-agent:${generation}-${crypto.randomUUID()}`, [generation]);

  const handleClose = () => {
    setGeneration((g) => g + 1);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-w-4xl p-0 h-[600px] flex flex-col">
        <DialogHeader className="border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-lg font-semibold">Create Agent</DialogTitle>
            <ProviderSelector value={provider} onChange={setProvider} />
          </div>
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
              prompt="/create-agent-mc"
              terminateOnClose
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

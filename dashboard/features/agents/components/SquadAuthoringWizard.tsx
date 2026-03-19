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

interface SquadAuthoringWizardProps {
  open: boolean;
  onClose: () => void;
  /** Called with the squad name when publishing succeeds */
  onPublished?: (squadName: string) => void;
}

export function SquadAuthoringWizard({ open, onClose }: SquadAuthoringWizardProps) {
  const [generation, setGeneration] = useState(0);
  const [provider, setProvider] = useState<WizardProvider>("claude-code");
  const scopeId = useMemo(() => `create-squad:${generation}-${crypto.randomUUID()}`, [generation]);

  const handleClose = () => {
    setGeneration((g) => g + 1);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent
        className="max-w-none w-[70vw] h-[90vh] p-0 flex flex-col"
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader className="border-b px-6 py-4 pr-12">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-lg font-semibold">Create Squad</DialogTitle>
            <ProviderSelector value={provider} onChange={setProvider} />
          </div>
          <DialogDescription className="sr-only">
            Interactive terminal session to design and publish a new squad blueprint.
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 min-h-0">
          {open && (
            <AgentTerminal
              agentName="nanobot"
              provider={provider}
              scopeId={scopeId}
              prompt="/create-squad-mc"
              terminateOnClose
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

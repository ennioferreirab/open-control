"use client";

import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useNanobotProvider } from "@/features/agents/hooks/useNanobotProvider";
import { AgentTerminal } from "./AgentTerminal";

interface SquadAuthoringWizardProps {
  open: boolean;
  onClose: () => void;
}

export function SquadAuthoringWizard({ open, onClose }: SquadAuthoringWizardProps) {
  const [generation, setGeneration] = useState(0);
  const scopeId = useMemo(() => `create-squad:${generation}-${crypto.randomUUID()}`, [generation]);
  const provider = useNanobotProvider();

  const handleClose = () => {
    setGeneration((g) => g + 1);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-w-4xl p-0 h-[600px] flex flex-col">
        <DialogHeader className="border-b px-6 py-4">
          <DialogTitle className="text-lg font-semibold">Create Squad</DialogTitle>
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
              prompt="Use the create-squad skill to walk me through designing a new squad."
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

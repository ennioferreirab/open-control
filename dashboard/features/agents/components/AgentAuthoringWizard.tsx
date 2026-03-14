"use client";

import { useCallback } from "react";
import { Check, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuthoringSession } from "@/features/agents/hooks/useAuthoringSession";
import { useCreateAuthoringDraft } from "@/features/agents/hooks/useCreateAuthoringDraft";
import { AuthoringConversationPanel } from "@/features/agents/components/AuthoringConversationPanel";
import { AuthoringPreviewPanel } from "@/features/agents/components/AuthoringPreviewPanel";

interface AgentAuthoringWizardProps {
  open: boolean;
  onClose: () => void;
  onPublished: (agentName: string) => void;
}

export function AgentAuthoringWizard({ open, onClose, onPublished }: AgentAuthoringWizardProps) {
  const { phase, transcript, draftGraph, isLoading, error, sendMessage } =
    useAuthoringSession("agent");

  const { isSaving, publishDraft } = useCreateAuthoringDraft();

  const isApproval = phase === "approval";

  const handlePublish = useCallback(async () => {
    const name = await publishDraft(draftGraph);
    if (name) {
      onPublished(name);
      onClose();
    }
  }, [publishDraft, draftGraph, onPublished, onClose]);

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-4xl p-0">
        <DialogHeader className="border-b px-6 py-4">
          <DialogTitle className="text-lg font-semibold">Create Agent</DialogTitle>
          <DialogDescription className="sr-only">
            Chat with the AI to design and publish your agent. The preview on the right updates live
            as you describe what you want.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-4 p-6 min-h-[420px]">
          <AuthoringConversationPanel
            transcript={transcript}
            isLoading={isLoading}
            error={error}
            onSend={sendMessage}
          />
          <AuthoringPreviewPanel draftGraph={draftGraph} phase={phase} readiness={0} />
        </div>

        <Separator />
        <div className="flex items-center justify-between px-6 py-4">
          <Button variant="ghost" onClick={onClose} aria-label="Cancel">
            Cancel
          </Button>

          {isApproval && (
            <Button onClick={handlePublish} disabled={isSaving}>
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Publishing…
                </>
              ) : (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Publish Agent
                </>
              )}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

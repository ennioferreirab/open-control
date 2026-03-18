"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Check } from "lucide-react";

interface AgentTextViewerModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  content: string;
  editable?: boolean;
  onSave?: (content: string) => Promise<void>;
}

export function AgentTextViewerModal({
  open,
  onClose,
  title,
  content,
  editable,
  onSave,
}: AgentTextViewerModalProps) {
  const [copied, setCopied] = useState(false);
  const [draft, setDraft] = useState(content);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Sync draft whenever the modal opens
  useEffect(() => {
    if (open) {
      setDraft(content);
      setSaved(false);
    }
  }, [open, content]);

  const handleOpenChange = useCallback(
    (o: boolean) => {
      if (!o) onClose();
    },
    [onClose],
  );

  const handleCopy = useCallback(() => {
    navigator.clipboard
      .writeText(editable ? draft : content)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => {});
  }, [content, draft, editable]);

  const handleSave = useCallback(async () => {
    if (!onSave) return;
    setSaving(true);
    try {
      await onSave(draft);
      setSaved(true);
      setTimeout(() => {
        setSaved(false);
        onClose();
      }, 800);
    } finally {
      setSaving(false);
    }
  }, [draft, onSave, onClose]);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-3xl w-full flex flex-col p-0 gap-0 [&>button]:hidden">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        {editable ? (
          <div className="flex-1 px-6 pb-4">
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="font-mono text-sm min-h-[50vh] resize-y"
            />
          </div>
        ) : (
          <ScrollArea className="flex-1 px-6 pb-4 max-h-[60vh]">
            <pre className="text-sm font-mono whitespace-pre-wrap break-words">{content}</pre>
          </ScrollArea>
        )}
        <DialogFooter className="px-6 py-4 border-t gap-2">
          <Button variant="outline" onClick={handleCopy}>
            {copied ? (
              <span className="flex items-center gap-1.5">
                <Check className="h-4 w-4 text-green-500" />
                Copied
              </span>
            ) : (
              "Copy"
            )}
          </Button>
          {editable && onSave ? (
            <>
              <Button variant="outline" onClick={onClose} disabled={saving}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={saving || saved}>
                {saved ? (
                  <span className="flex items-center gap-1.5">
                    <Check className="h-4 w-4 text-green-500" />
                    Saved
                  </span>
                ) : saving ? (
                  "Saving…"
                ) : (
                  "Save"
                )}
              </Button>
            </>
          ) : (
            <Button onClick={onClose}>Close</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

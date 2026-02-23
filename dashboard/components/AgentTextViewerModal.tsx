"use client";
import { useCallback, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";

interface AgentTextViewerModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  content: string;
}

export function AgentTextViewerModal({ open, onClose, title, content }: AgentTextViewerModalProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => {});
  }, [content]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl w-full flex flex-col p-0 gap-0 [&>button]:hidden">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <ScrollArea className="flex-1 px-6 pb-4 max-h-[60vh]">
          <pre className="text-sm font-mono whitespace-pre-wrap break-words">{content}</pre>
        </ScrollArea>
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
          <Button onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

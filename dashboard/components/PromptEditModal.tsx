"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Info } from "lucide-react";

function HighlightedPromptTextarea({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const backdropRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleScroll = () => {
    if (backdropRef.current && textareaRef.current) {
      backdropRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  };

  const highlighted = useMemo(() => {
    const parts = value.split(/(\{\{\w+\}\})/);
    return parts.map((part, i) => {
      if (/^\{\{\w+\}\}$/.test(part)) {
        return (
          <mark
            key={i}
            style={{
              background: "oklch(0.905 0.093 95.31 / 0.55)",
              color: "transparent",
              borderRadius: "3px",
              fontWeight: "bold",
            }}
          >
            {part}
          </mark>
        );
      }
      return (
        <span key={i} style={{ color: "transparent" }}>
          {part}
        </span>
      );
    });
  }, [value]);

  return (
    <div className="relative rounded-md border border-input shadow-sm focus-within:ring-1 focus-within:ring-ring">
      <div
        ref={backdropRef}
        aria-hidden="true"
        className="absolute inset-0 overflow-hidden pointer-events-none px-3 py-2 font-mono text-sm whitespace-pre-wrap break-words leading-normal"
      >
        {highlighted}
      </div>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={handleScroll}
        className="relative block w-full bg-transparent px-3 py-2 font-mono text-sm placeholder:text-muted-foreground focus-visible:outline-none min-h-[300px] resize-y leading-normal"
      />
    </div>
  );
}

export type PromptVariable = { name: string; value: string };

interface PromptEditModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (prompt: string, variables: PromptVariable[]) => void;
  initialPrompt: string;
  initialVariables: PromptVariable[];
}

function detectVariables(prompt: string, existing: PromptVariable[]): PromptVariable[] {
  const detected = new Set<string>();
  const regex = /\{\{(\w+)\}\}/g;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(prompt)) !== null) {
    detected.add(m[1]);
  }
  // Preserve existing order; append truly new variables at the end
  const result: PromptVariable[] = existing.filter((v) => detected.has(v.name));
  const existingNames = new Set(existing.map((v) => v.name));
  for (const name of detected) {
    if (!existingNames.has(name)) {
      result.push({ name, value: "" });
    }
  }
  return result;
}

export function PromptEditModal({
  open,
  onClose,
  onSave,
  initialPrompt,
  initialVariables,
}: PromptEditModalProps) {
  const [localPrompt, setLocalPrompt] = useState(initialPrompt);
  const [localVariables, setLocalVariables] = useState<PromptVariable[]>(initialVariables);
  const prevOpenRef = useRef(false);

  // Re-initialize only when modal transitions from closed → open,
  // not on every render where initialPrompt/initialVariables reference changes.
  useEffect(() => {
    if (open && !prevOpenRef.current) {
      setLocalPrompt(initialPrompt);
      setLocalVariables(initialVariables);
    }
    prevOpenRef.current = open;
  }, [open, initialPrompt, initialVariables]);

  const handlePromptChange = useCallback((value: string) => {
    setLocalPrompt(value);
    setLocalVariables((prev) => detectVariables(value, prev));
  }, []);

  const handleValueChange = useCallback((name: string, value: string) => {
    setLocalVariables((prev) =>
      prev.map((v) => (v.name === name ? { ...v, value } : v)),
    );
  }, []);

  const handleSave = useCallback(() => {
    onSave(localPrompt, localVariables);
    onClose();
  }, [localPrompt, localVariables, onSave, onClose]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl w-full flex flex-col p-0 gap-0 [&>button]:hidden">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle>Edit Prompt</DialogTitle>
        </DialogHeader>

        <div className="flex-1 px-6 pb-4 space-y-4 overflow-y-auto">
          <HighlightedPromptTextarea
            value={localPrompt}
            onChange={handlePromptChange}
          />

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium">Variables</p>
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Info className="h-3.5 w-3.5" />
                {"Supports {{variable}} interpolation"}
              </span>
            </div>
            <div className="border rounded-md overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 border-b">
                    <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground w-1/2">
                      Variable
                    </th>
                    <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground w-1/2">
                      Value
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {localVariables.length > 0 ? (
                    localVariables.map((v, i) => (
                      <tr key={v.name} className={i > 0 ? "border-t" : ""}>
                        <td className="px-3 py-2">
                          <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                            {`{{${v.name}}}`}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <Input
                            value={v.value}
                            onChange={(e) => handleValueChange(v.name, e.target.value)}
                            placeholder={`Value for ${v.name}`}
                            className="h-7 text-sm"
                          />
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={2} className="px-3 py-3 text-center text-xs text-muted-foreground">
                        {"Type {{name}} in the prompt to create variables"}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <DialogFooter className="px-6 py-4 border-t gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

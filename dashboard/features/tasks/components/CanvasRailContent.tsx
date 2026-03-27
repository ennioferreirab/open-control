"use client";

import { Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { getInitials, getAvatarColor } from "@/lib/agentUtils";

export interface SelectedStepDetail {
  id: string;
  number: number;
  name: string;
  agent: string;
  status: string;
  hasLiveSession: boolean;
}

export interface ThreadMiniMessage {
  id: string;
  agent: string;
  text: string;
}

interface CanvasRailContentProps {
  selectedStep: SelectedStepDetail | null;
  threadPreview: ThreadMiniMessage[];
  onOpenLive: (stepId: string) => void;
  onFilterThread: (stepId: string) => void;
  onViewThread: () => void;
}

export function CanvasRailContent({
  selectedStep,
  threadPreview,
  onOpenLive,
  onFilterThread,
  onViewThread,
}: CanvasRailContentProps) {
  return (
    <>
      {/* Selected node detail */}
      {selectedStep && (
        <div className="border-b border-border px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <span
              className={cn(
                "flex-shrink-0 rounded-full flex items-center justify-center text-[10px] font-medium h-5 w-5 text-white",
                getAvatarColor(selectedStep.agent),
              )}
            >
              {selectedStep.number}
            </span>
            <span className="text-xs font-medium text-foreground truncate flex-1">
              {selectedStep.name}
            </span>
            <span className="text-[10px] text-muted-foreground">selected</span>
          </div>
          <div className="space-y-1 text-[11px]">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Agent</span>
              <span className="text-foreground">{selectedStep.agent}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status</span>
              <span className="text-foreground capitalize">{selectedStep.status}</span>
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            {selectedStep.hasLiveSession && (
              <button
                type="button"
                onClick={() => onOpenLive(selectedStep.id)}
                className="flex-1 h-7 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium inline-flex items-center justify-center gap-1"
              >
                <Zap className="h-3 w-3" />
                Open Live
              </button>
            )}
            <button
              type="button"
              onClick={() => onFilterThread(selectedStep.id)}
              className="flex-1 h-7 rounded-md bg-muted hover:bg-muted/80 text-foreground text-xs font-medium inline-flex items-center justify-center"
            >
              Filter Thread
            </button>
          </div>
        </div>
      )}

      {/* Thread mini-preview */}
      {threadPreview.length > 0 && (
        <div className="border-b border-border px-4 py-3">
          <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 mb-2">
            Thread
          </div>
          <div className="space-y-1.5">
            {threadPreview.map((msg) => (
              <div key={msg.id} className="flex items-start gap-2">
                <span
                  className={cn(
                    "flex-shrink-0 rounded-full flex items-center justify-center text-[8px] font-medium h-4 w-4 text-white mt-0.5",
                    getAvatarColor(msg.agent),
                  )}
                >
                  {getInitials(msg.agent)}
                </span>
                <p className="text-[11px] text-muted-foreground line-clamp-2 leading-snug">
                  {msg.text}
                </p>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={onViewThread}
            className="mt-2 text-[11px] text-primary hover:underline"
          >
            View full thread
          </button>
        </div>
      )}
    </>
  );
}

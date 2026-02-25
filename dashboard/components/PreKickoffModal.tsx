"use client";

import { useEffect, useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";
import { STATUS_COLORS } from "@/lib/constants";
import { PlanEditor } from "./PlanEditor";
import { PlanChatPanel } from "./PlanChatPanel";
import type { ExecutionPlan } from "@/lib/types";

interface PreKickoffModalProps {
  taskId: Id<"tasks"> | null;
  open: boolean;
  onClose: () => void;
}

export function PreKickoffModal({ taskId, open, onClose }: PreKickoffModalProps) {
  const task = useQuery(api.tasks.getById, taskId ? { taskId } : "skip");
  const [localPlan, setLocalPlan] = useState<ExecutionPlan | null>(null);

  // Reset localPlan when taskId changes to prevent stale plan from a previous task
  useEffect(() => {
    setLocalPlan(null);
  }, [taskId]);

  const colors = STATUS_COLORS["reviewing_plan"];

  // Derive initial plan from task; prefer local edits once set
  const executionPlan = (localPlan ?? task?.executionPlan ?? null) as ExecutionPlan | null;

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent
        className="fixed inset-4 z-50 flex flex-col max-w-none translate-x-0 translate-y-0 rounded-lg border bg-background shadow-lg h-[calc(100vh-2rem)] w-[calc(100vw-2rem)]"
      >
        {/* Accessible hidden title and description for Radix a11y */}
        <DialogTitle className="sr-only">Pre-Kickoff Plan Review</DialogTitle>
        <DialogDescription className="sr-only">
          Review and edit the execution plan before kick-off
        </DialogDescription>

        {/* Custom header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <h2 className="text-lg font-semibold text-foreground truncate max-w-[400px]">
              {task?.title ?? "Loading..."}
            </h2>
            <Badge
              variant="outline"
              className={`text-xs shrink-0 ${colors.bg} ${colors.text} border-0`}
            >
              reviewing plan
            </Badge>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="default"
              className="bg-green-500 hover:bg-green-600 text-white opacity-50 cursor-not-allowed"
              disabled
            >
              Kick-off
            </Button>
            <DialogClose asChild>
              <button
                onClick={onClose}
                className="rounded-sm p-1 opacity-70 hover:opacity-100 transition-opacity focus:outline-none focus:ring-2 focus:ring-ring"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </DialogClose>
          </div>
        </div>

        {/* Two-panel body */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Left panel: Plan Editor (60% width) */}
          <div className="flex-[3] min-w-0 border-r border-border overflow-y-auto p-4">
            <h3 className="text-sm font-semibold text-foreground mb-3">Plan Editor</h3>
            {executionPlan && taskId ? (
              <PlanEditor
                plan={executionPlan}
                taskId={taskId}
                onPlanChange={setLocalPlan}
              />
            ) : (
              <p className="text-sm text-muted-foreground">Loading plan...</p>
            )}
          </div>

          {/* Right panel: Chat (40% width) */}
          <div className="flex-[2] min-w-0 flex flex-col overflow-hidden">
            <div className="px-4 pt-4 pb-2 shrink-0">
              <h3 className="text-sm font-semibold text-foreground">Lead Agent Chat</h3>
            </div>
            {taskId ? (
              <PlanChatPanel taskId={taskId} />
            ) : (
              <p className="text-sm text-muted-foreground px-4">
                No task selected.
              </p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

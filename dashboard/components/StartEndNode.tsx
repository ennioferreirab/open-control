"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { Play, Square } from "lucide-react";
import { cn } from "@/lib/utils";

export type StartNodeType = Node<Record<string, never>, "start">;
export type EndNodeType   = Node<Record<string, never>, "end">;

function StartNodeComponent({ selected }: NodeProps<StartNodeType>) {
  return (
    <div
      className={cn(
        "rounded-full border-2 bg-background px-4 py-2 shadow-sm flex items-center gap-1.5",
        "border-green-500",
        selected && "ring-2 ring-green-500/30"
      )}
    >
      <Play className="h-3.5 w-3.5 text-green-500 fill-green-500" />
      <span className="text-xs font-medium text-green-600">START</span>
      <Handle
        type="source"
        position={Position.Right}
        className="!opacity-0 !pointer-events-none"
      />
    </div>
  );
}

function EndNodeComponent({ selected }: NodeProps<EndNodeType>) {
  return (
    <div
      className={cn(
        "rounded-full border-2 bg-background px-4 py-2 shadow-sm flex items-center gap-1.5",
        "border-red-500",
        selected && "ring-2 ring-red-500/30"
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!opacity-0 !pointer-events-none"
      />
      <Square className="h-3.5 w-3.5 text-red-500 fill-red-500" />
      <span className="text-xs font-medium text-red-600">END</span>
    </div>
  );
}

export const StartNode = memo(StartNodeComponent);
export const EndNode = memo(EndNodeComponent);

"use client";

import { useEffect, useRef, useState } from "react";
import * as motion from "motion/react-client";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TaskCard } from "@/components/TaskCard";
import { Doc, Id } from "../convex/_generated/dataModel";
import { Eraser, List } from "lucide-react";

interface KanbanColumnProps {
  title: string;
  status: string;
  tasks: Doc<"tasks">[];
  accentColor: string;
  onTaskClick?: (taskId: Id<"tasks">) => void;
  hitlCount?: number;
  onClear?: () => void;
  clearDisabled?: boolean;
  onViewAll?: () => void;
}

export function KanbanColumn({
  title,
  tasks,
  accentColor,
  onTaskClick,
  hitlCount = 0,
  onClear,
  clearDisabled,
  onViewAll,
}: KanbanColumnProps) {
  const prevCountRef = useRef(hitlCount);
  const [isPulsing, setIsPulsing] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  useEffect(() => {
    if (hitlCount > prevCountRef.current) {
      const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      if (!motionQuery.matches) {
        setIsPulsing(true);
        const timer = setTimeout(() => setIsPulsing(false), 600);
        return () => clearTimeout(timer);
      }
    }
    prevCountRef.current = hitlCount;
  }, [hitlCount]);

  return (
    <div className="flex flex-col min-h-0">
      <div className="flex items-center gap-2 mb-3 px-1">
        <div className={`w-2 h-2 rounded-full ${accentColor}`} />
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <Badge variant="secondary" className="text-xs">
          {tasks.length}
        </Badge>
        {hitlCount > 0 && (
          <span
            data-testid="hitl-badge"
            className={`bg-amber-500 text-white text-xs font-medium rounded-full px-1.5 min-w-[20px] text-center ${isPulsing ? "animate-pulse-once" : ""}`}
          >
            {hitlCount}
          </span>
        )}
        {onClear && (
          <Eraser
            aria-label="Clear done tasks"
            className={`h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer${clearDisabled ? " pointer-events-none opacity-40" : ""}`}
            onClick={() => setShowClearConfirm(true)}
          />
        )}
        {onViewAll && (
          <List
            aria-label="View all done tasks"
            className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            onClick={onViewAll}
          />
        )}
      </div>
      {showClearConfirm && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="overflow-hidden px-1 mb-2"
        >
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Clear all done tasks?</span>
            <Button
              size="sm"
              variant="destructive"
              className="text-xs h-6 px-2"
              onClick={() => {
                onClear?.();
                setShowClearConfirm(false);
              }}
            >
              Yes
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-xs h-6 px-2"
              onClick={() => setShowClearConfirm(false)}
            >
              Cancel
            </Button>
          </div>
        </motion.div>
      )}
      <ScrollArea className="flex-1">
        {tasks.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">No tasks</p>
        ) : (
          <div className="flex flex-col gap-2 pr-2">
            {tasks.map((task) => (
              <TaskCard
                key={task._id}
                task={task}
                onClick={onTaskClick ? () => onTaskClick(task._id) : undefined}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}

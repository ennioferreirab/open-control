"use client";

import type { ReactNode } from "react";
import { ChevronsLeft, ChevronsRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { TagChip } from "@/components/TagChip";
import type { TAG_COLORS } from "@/lib/constants";

interface ContextRailProps {
  title: string;
  tags?: string[];
  tagColorMap?: Record<string, keyof typeof TAG_COLORS>;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  children: ReactNode;
  className?: string;
}

export function ContextRail({
  title,
  tags,
  tagColorMap,
  isCollapsed = false,
  onToggleCollapse,
  children,
  className,
}: ContextRailProps) {
  return (
    <div
      className={cn(
        "flex flex-col border-l border-border bg-background overflow-hidden transition-[width] duration-200",
        isCollapsed ? "w-12" : "w-[300px]",
        className,
      )}
      data-testid="context-rail"
    >
      {isCollapsed ? (
        <div className="flex flex-col items-center pt-3">
          <button
            type="button"
            onClick={onToggleCollapse}
            className="p-1.5 rounded-md hover:bg-muted transition-colors"
            aria-label="Expand rail"
          >
            <ChevronsRight className="h-3 w-3 text-muted-foreground" />
          </button>
        </div>
      ) : (
        <>
          <div className="border-b border-border px-4 py-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
                Context
              </span>
              {onToggleCollapse && (
                <button
                  type="button"
                  onClick={onToggleCollapse}
                  className="p-0.5 rounded-md hover:bg-muted transition-colors"
                  aria-label="Collapse rail"
                >
                  <ChevronsLeft className="h-3 w-3 text-muted-foreground" />
                </button>
              )}
            </div>
            <h3 className="text-sm font-semibold text-foreground leading-snug">{title}</h3>
            {tags && tags.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {tags.map((tag) => (
                  <TagChip key={tag} label={tag} color={tagColorMap?.[tag]} size="sm" />
                ))}
              </div>
            )}
          </div>
          <div className="flex-1 overflow-y-auto">{children}</div>
        </>
      )}
    </div>
  );
}

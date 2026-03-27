"use client";

import { useState, type ReactNode } from "react";
import { ChevronRight, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface RailSectionProps {
  icon: LucideIcon;
  label: string;
  badge?: string | number;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
  trailing?: ReactNode;
}

export function RailSection({
  icon: Icon,
  label,
  badge,
  defaultOpen = false,
  children,
  className,
  trailing,
}: RailSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={className}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full cursor-pointer items-center gap-2 px-4 py-3 transition-colors hover:bg-card/50"
        data-testid="rail-section-header"
      >
        <Icon className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
        <span className="flex-1 text-left text-xs font-semibold text-foreground">{label}</span>
        {badge !== undefined && (
          <span className="rounded-full bg-muted px-1.5 text-[10px] font-semibold text-muted-foreground">
            {badge}
          </span>
        )}
        {trailing}
        <ChevronRight
          className={cn(
            "h-2.5 w-2.5 flex-shrink-0 text-muted-foreground transition-transform duration-150",
            open && "rotate-90",
          )}
        />
      </button>
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-150 ease-out",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
        data-testid="rail-section-content"
        data-state={open ? "open" : "closed"}
      >
        <div className="overflow-hidden">{children}</div>
      </div>
    </div>
  );
}

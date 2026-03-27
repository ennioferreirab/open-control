"use client";

import { cn } from "@/lib/utils";
import { MessageCircle, LayoutGrid } from "lucide-react";

interface ViewToggleProps {
  value: "thread" | "canvas";
  onChange: (value: "thread" | "canvas") => void;
  className?: string;
}

const options = [
  { value: "thread" as const, label: "Thread", icon: MessageCircle },
  { value: "canvas" as const, label: "Canvas", icon: LayoutGrid },
];

export function ViewToggle({ value, onChange, className }: ViewToggleProps) {
  return (
    <div
      role="group"
      aria-label="View mode"
      className={cn("bg-card border border-border rounded-lg p-[3px] flex gap-[1px]", className)}
    >
      {options.map((option) => {
        const Icon = option.icon;
        const isActive = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={isActive}
            onClick={() => onChange(option.value)}
            className={cn(
              "px-3.5 py-1 text-xs font-medium flex items-center gap-1.5 rounded-[5px] transition-colors",
              isActive ? "bg-primary text-white" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

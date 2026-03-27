import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface ParallelBracketProps {
  children: ReactNode;
  className?: string;
}

export function ParallelBracket({ children, className }: ParallelBracketProps) {
  return (
    <div className={cn("flex flex-row", className)} data-testid="parallel-bracket">
      <div className="w-0.5 bg-primary/30 rounded-full my-0.5" />
      <div className="flex flex-col flex-1">
        <span className="text-[9px] font-bold uppercase tracking-wider text-primary/50 px-1.5 py-0.5">
          Parallel
        </span>
        <div className="flex flex-col gap-0.5 flex-1">{children}</div>
      </div>
    </div>
  );
}

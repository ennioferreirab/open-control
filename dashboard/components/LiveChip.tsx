
import { cn } from "@/lib/utils";
import { Zap } from "lucide-react";

interface LiveChipProps {
  className?: string;
  size?: "sm" | "md";
}

export function LiveChip({ className, size = "sm" }: LiveChipProps) {
  return (
    <span
      className={cn(
        "bg-success/10 text-success border border-success/15 rounded-full px-1.5 py-0.5 text-[9px] font-medium flex items-center gap-1",
        className,
      )}
    >
      <Zap className={size === "sm" ? "h-[9px] w-[9px]" : "h-[11px] w-[11px]"} />
      Live
    </span>
  );
}

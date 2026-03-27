import { cn } from "@/lib/utils";
import { STATUS_COLORS, STEP_STATUS_COLORS } from "@/lib/constants";

interface StatusBadgeProps {
  status: string;
  type?: "task" | "step";
  size?: "sm" | "md";
  className?: string;
}

function formatStatusLabel(status: string): string {
  return status.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/**
 * Derives a dot background class (e.g. "bg-teal-500") from a border class string.
 * Handles both simple ("border-l-teal-500") and compound ("border-r-[3px] border-r-teal-500/30") formats.
 * Strips opacity suffixes so the dot renders at full opacity.
 */
function dotClassFromBorder(borderClass: string): string {
  // Try the color part of a compound border (e.g. "border-r-teal-500/30" → "teal-500")
  const compoundMatch = borderClass.match(/border-[a-z]+-([a-z]+-\d+)(?:\/\d+)?(?:\s|$)/);
  if (compoundMatch) return `bg-${compoundMatch[1]}`;
  // Simple single-class fallback (e.g. "border-l-teal-500")
  const simpleMatch = borderClass.match(/^border-[a-z]+-(.+)$/);
  return simpleMatch ? `bg-${simpleMatch[1]}` : "bg-current";
}

export function StatusBadge({ status, type = "task", size = "sm", className }: StatusBadgeProps) {
  const colorMap = type === "task" ? STATUS_COLORS : STEP_STATUS_COLORS;
  const colors = colorMap[status as keyof typeof colorMap];
  const statusLabel = formatStatusLabel(status);
  const dotClass = colors ? dotClassFromBorder(colors.border) : "bg-muted-foreground";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5",
        size === "sm" ? "text-[10px]" : "text-xs",
        colors ? `${colors.bg} ${colors.text}` : "bg-muted text-muted-foreground",
        className,
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 flex-shrink-0 rounded-full",
          dotClass,
          "dark:shadow-[0_0_6px_currentColor]",
        )}
      />
      {statusLabel}
    </span>
  );
}

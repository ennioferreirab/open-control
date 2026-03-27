import { cn } from "@/lib/utils";
import { Plus } from "lucide-react";

interface AttachButtonProps {
  onClick?: () => void;
  className?: string;
  disabled?: boolean;
}

export function AttachButton({ onClick, className, disabled }: AttachButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "w-8 h-8 rounded-full bg-card border border-border text-muted-foreground flex items-center justify-center hover:bg-muted hover:text-foreground transition-colors",
        disabled && "opacity-50 cursor-not-allowed",
        className,
      )}
    >
      <Plus className="h-4 w-4" />
    </button>
  );
}


import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Settings } from "lucide-react";

interface ChatBubbleProps {
  authorType: "agent" | "user" | "system";
  messageType?: string;
  agentColor?: string;
  stepLabel?: string;
  stepLabelColor?: string;
  children: ReactNode;
  className?: string;
}

export function ChatBubble({
  authorType,
  agentColor,
  stepLabel,
  stepLabelColor,
  children,
  className,
}: ChatBubbleProps) {
  if (authorType === "system") {
    return (
      <div
        className={cn(
          "self-stretch bg-muted border border-border/50 rounded-md text-sm text-muted-foreground py-1.5 px-3.5 flex items-start gap-2",
          className,
        )}
        data-testid="chat-bubble-system"
      >
        <Settings className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">{children}</div>
      </div>
    );
  }

  if (authorType === "user") {
    return (
      <div
        className={cn(
          "self-end max-w-[65%] bg-primary/[0.08] border border-primary/[0.12] rounded-xl rounded-br-[4px] p-3",
          className,
        )}
        data-testid="chat-bubble-user"
      >
        {children}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "self-start max-w-[85%] bg-card border border-border border-l-2 rounded-xl rounded-bl-[4px] p-3",
        className,
      )}
      style={agentColor ? { borderLeftColor: agentColor } : undefined}
      data-testid="chat-bubble-agent"
    >
      {stepLabel && (
        <span
          className="text-[9px] px-1 py-0.5 rounded-full inline-block mb-1.5"
          style={
            stepLabelColor
              ? {
                  backgroundColor: `${stepLabelColor}1A`,
                  color: stepLabelColor,
                }
              : undefined
          }
          data-testid="step-pill"
        >
          {stepLabel}
        </span>
      )}
      {children}
    </div>
  );
}

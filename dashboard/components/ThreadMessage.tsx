"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { CheckCircle2, XCircle } from "lucide-react";
import { Doc } from "../convex/_generated/dataModel";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface ThreadMessageProps {
  message: Doc<"messages">;
}

function getInitials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

function getMessageStyles(messageType: string, authorType: string) {
  switch (messageType) {
    case "review_feedback":
      return { bg: "bg-amber-50", label: "Review", labelColor: "text-amber-600" };
    case "approval":
      return { bg: "bg-green-50", label: "Approved", labelColor: "text-green-600" };
    case "denial":
      return { bg: "bg-red-50", label: "Denied", labelColor: "text-red-600" };
    case "system_event":
      return { bg: "bg-muted", label: null, labelColor: "" };
    default:
      if (authorType === "user") return { bg: "bg-blue-50", label: null, labelColor: "" };
      return { bg: "bg-background", label: null, labelColor: "" };
  }
}

export function ThreadMessage({ message }: ThreadMessageProps) {
  const styles = getMessageStyles(message.messageType, message.authorType);
  const isSystem = message.authorType === "system" || message.messageType === "system_event";
  const isApproval = message.messageType === "approval";
  const isDenial = message.messageType === "denial";

  return (
    <div className={`flex gap-2 p-2 rounded-md ${styles.bg}`}>
      <Avatar className="h-6 w-6 shrink-0">
        <AvatarFallback className="text-xs">
          {getInitials(message.authorName)}
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-foreground">
            {message.authorName}
          </span>
          {styles.label && (
            <span className={`text-xs font-medium ${styles.labelColor}`}>
              {styles.label}
            </span>
          )}
          <span className="text-xs text-muted-foreground">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <div className="flex items-start gap-1 mt-0.5">
          {isApproval && (
            <CheckCircle2 className="h-3.5 w-3.5 text-green-600 shrink-0 mt-0.5" />
          )}
          {isDenial && (
            <XCircle className="h-3.5 w-3.5 text-red-600 shrink-0 mt-0.5" />
          )}
          {isSystem || message.authorType === "user" ? (
            <p className={`text-sm text-muted-foreground ${isSystem ? "italic" : ""}`}>
              {message.content}
            </p>
          ) : (
            <MarkdownRenderer
              content={message.content}
              className="text-muted-foreground"
            />
          )}
        </div>
      </div>
    </div>
  );
}

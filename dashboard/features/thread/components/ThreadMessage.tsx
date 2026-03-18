"use client";

import { memo } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AlertTriangle, CheckCircle2, XCircle, MessageCircle } from "lucide-react";
import { Doc } from "@/convex/_generated/dataModel";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { ArtifactRenderer } from "@/components/ArtifactRenderer";
import { FileChip } from "@/components/FileChip";
import { STRUCTURED_MESSAGE_TYPE } from "@/lib/constants";

interface ThreadMessageProps {
  message: Doc<"messages">;
  steps?: Doc<"steps">[];
  onArtifactClick?: (artifactPath: string, sourceTaskId?: Doc<"messages">["taskId"]) => void;
  taskIdOverride?: Doc<"messages">["taskId"];
}

function resolveStepTitle(message: Doc<"messages">, steps?: Doc<"steps">[]): string | undefined {
  if (!message.stepId || !steps) return undefined;
  return steps.find((step) => step._id === message.stepId)?.title;
}

function areArtifactsEqual(
  previous: Doc<"messages">["artifacts"],
  next: Doc<"messages">["artifacts"],
): boolean {
  if (previous === next) return true;
  if ((previous?.length ?? 0) !== (next?.length ?? 0)) return false;

  return (previous ?? []).every((artifact, index) => {
    const candidate = next?.[index];
    return (
      candidate?.path === artifact.path &&
      candidate?.action === artifact.action &&
      candidate?.description === artifact.description
    );
  });
}

function areFileAttachmentsEqual(
  previous: Doc<"messages">["fileAttachments"],
  next: Doc<"messages">["fileAttachments"],
): boolean {
  if (previous === next) return true;
  if ((previous?.length ?? 0) !== (next?.length ?? 0)) return false;

  return (previous ?? []).every((attachment, index) => {
    const candidate = next?.[index];
    return candidate?.name === attachment.name && candidate?.size === attachment.size;
  });
}

function areMessagesRenderEquivalent(previous: Doc<"messages">, next: Doc<"messages">): boolean {
  return (
    previous._id === next._id &&
    previous.authorName === next.authorName &&
    previous.authorType === next.authorType &&
    previous.content === next.content &&
    previous.messageType === next.messageType &&
    previous.type === next.type &&
    previous.timestamp === next.timestamp &&
    previous.taskId === next.taskId &&
    previous.stepId === next.stepId &&
    areArtifactsEqual(previous.artifacts, next.artifacts) &&
    areFileAttachmentsEqual(previous.fileAttachments, next.fileAttachments)
  );
}

function areThreadMessagePropsEqual(
  previous: ThreadMessageProps,
  next: ThreadMessageProps,
): boolean {
  return (
    previous.onArtifactClick === next.onArtifactClick &&
    previous.taskIdOverride === next.taskIdOverride &&
    areMessagesRenderEquivalent(previous.message, next.message) &&
    resolveStepTitle(previous.message, previous.steps) ===
      resolveStepTitle(next.message, next.steps)
  );
}

function getInitials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

type MessageStyles = {
  bg: string;
  label: string | null;
  labelColor: string;
};

function getLegacyMessageStyles(messageType: string, authorType: string): MessageStyles {
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

function getMessageStyles(message: Doc<"messages">): MessageStyles {
  // Prefer new structured type if present
  if (message.type) {
    switch (message.type) {
      case STRUCTURED_MESSAGE_TYPE.STEP_COMPLETION:
        return { bg: "bg-background", label: "Step Complete", labelColor: "text-green-600" };
      case STRUCTURED_MESSAGE_TYPE.SYSTEM_ERROR:
        return { bg: "bg-red-50", label: "Error", labelColor: "text-red-600" };
      case STRUCTURED_MESSAGE_TYPE.LEAD_AGENT_CHAT:
        return { bg: "bg-indigo-50", label: "Lead Agent", labelColor: "text-indigo-600" };
      case STRUCTURED_MESSAGE_TYPE.USER_MESSAGE:
        return { bg: "bg-blue-50", label: null, labelColor: "" };
      case STRUCTURED_MESSAGE_TYPE.COMMENT:
        return { bg: "bg-slate-50", label: "Comment", labelColor: "text-slate-500" };
    }
  }
  // Fall back to legacy messageType
  return getLegacyMessageStyles(message.messageType, message.authorType);
}

function ThreadMessageComponent({
  message,
  steps,
  onArtifactClick,
  taskIdOverride,
}: ThreadMessageProps) {
  const styles = getMessageStyles(message);
  const resolvedTaskId = taskIdOverride ?? message.taskId;
  // Lead Agent messages have authorType "system" but should render as Markdown
  // (not plain italic text). Exclude lead_agent_chat from the isSystem flag
  // so they get MarkdownRenderer treatment.
  const isLeadAgentMessage =
    message.type === STRUCTURED_MESSAGE_TYPE.LEAD_AGENT_CHAT;
  const isSystem =
    !isLeadAgentMessage &&
    (message.authorType === "system" || message.messageType === "system_event");
  const isSystemError = message.type === STRUCTURED_MESSAGE_TYPE.SYSTEM_ERROR;
  const isComment = message.type === STRUCTURED_MESSAGE_TYPE.COMMENT;
  const isApproval = message.messageType === "approval";
  const isDenial = message.messageType === "denial";

  // Resolve step title for step_completion messages (Option A: passed from parent)
  const stepTitle = resolveStepTitle(message, steps);

  return (
    <div className={`flex w-full min-w-0 max-w-full gap-2 rounded-md p-2 ${styles.bg}`}>
      <Avatar className="h-6 w-6 shrink-0">
        <AvatarFallback className="text-xs">{getInitials(message.authorName)}</AvatarFallback>
      </Avatar>
      <div className="flex-1 min-w-0 max-w-full overflow-hidden">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium text-foreground flex items-center gap-1">
            {isComment && <MessageCircle className="h-3 w-3 text-slate-500 shrink-0" />}
            {message.authorName}
          </span>
          {styles.label && (
            <span className={`text-xs font-medium ${styles.labelColor}`}>{styles.label}</span>
          )}
          {isSystemError && <AlertTriangle className="h-3.5 w-3.5 text-red-600 shrink-0" />}
          <span className="text-xs text-muted-foreground">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        </div>

        {/* Step reference badge for step_completion messages */}
        {stepTitle && <p className="text-xs text-muted-foreground mt-0.5">Step: {stepTitle}</p>}

        <div className="flex items-start gap-1 mt-0.5">
          {isApproval && <CheckCircle2 className="h-3.5 w-3.5 text-green-600 shrink-0 mt-0.5" />}
          {isDenial && <XCircle className="h-3.5 w-3.5 text-red-600 shrink-0 mt-0.5" />}
          {isSystem || message.authorType === "user" ? (
            <p
              className={`text-sm text-muted-foreground break-words [overflow-wrap:anywhere] ${isSystem || isSystemError ? "italic" : ""}`}
            >
              {message.content}
            </p>
          ) : (
            <MarkdownRenderer content={message.content} className="text-muted-foreground" />
          )}
        </div>

        {/* Render artifacts if present */}
        {message.artifacts && message.artifacts.length > 0 && (
          <ArtifactRenderer
            artifacts={message.artifacts}
            onArtifactClick={
              onArtifactClick
                ? (artifact) => onArtifactClick(artifact.path, resolvedTaskId)
                : undefined
            }
          />
        )}

        {/* Render file attachments if present */}
        {message.fileAttachments && message.fileAttachments.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {message.fileAttachments.map((fa) => (
              <FileChip
                key={fa.name}
                name={fa.name}
                size={fa.size}
                href={`/api/tasks/${resolvedTaskId}/files/attachments/${encodeURIComponent(fa.name)}`}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export const ThreadMessage = memo(ThreadMessageComponent, areThreadMessagePropsEqual);
ThreadMessage.displayName = "ThreadMessage";

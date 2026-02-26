"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { Doc } from "../convex/_generated/dataModel";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SendHorizontal, RotateCcw } from "lucide-react";
import { AgentMentionAutocomplete } from "./AgentMentionAutocomplete";

interface ThreadInputProps {
  task: Doc<"tasks">;
  onMessageSent?: () => void;
}

// Statuses where the user cannot interact with the task thread at all.
// Note: "in_progress" and "review" (awaitingKickoff) are NOT blocked — users
// can send plan-chat messages to the Lead Agent in those states (Story 7.3).
const BLOCKED_STATUSES = ["retrying"];

export function ThreadInput({ task, onMessageSent }: ThreadInputProps) {
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [error, setError] = useState("");
  const [selectedAgent, setSelectedAgent] = useState(
    task.assignedAgent ?? ""
  );
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [mentionStartIndex, setMentionStartIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const sendMessage = useMutation(api.messages.sendThreadMessage);
  const postPlanMessage = useMutation(api.messages.postUserPlanMessage);
  const restoreTask = useMutation(api.tasks.restore);
  const agents = useQuery(api.agents.list);
  const board = useQuery(
    api.boards.getById,
    task.boardId ? { boardId: task.boardId } : "skip"
  );

  // Sync selectedAgent when task.assignedAgent changes (H3 fix: useEffect instead of render-time setState)
  useEffect(() => {
    if (task.assignedAgent && !isSubmitting) {
      setSelectedAgent(task.assignedAgent);
    }
  }, [task.assignedAgent, isSubmitting]);

  // Don't render for manual tasks
  if (task.isManual) return null;

  // Plan-chat mode: task is in_progress, or review+awaitingKickoff.
  // In this mode the user can chat with the Lead Agent to modify the plan.
  // We use postUserPlanMessage (no status transition, no plan clear).
  const taskAny = task as any;
  const isPlanChatMode =
    task.status === "in_progress" ||
    (task.status === "review" && taskAny.awaitingKickoff === true);

  const isBlocked = BLOCKED_STATUSES.includes(task.status);
  const canSend = content.trim().length > 0 && !isSubmitting && (isPlanChatMode || !!selectedAgent);

  // Filter agents by board's enabledAgents (empty = all agents eligible)
  const enabledAgentNames = board?.enabledAgents ?? [];
  const filteredAgents = agents?.filter((a) => {
    if (!a.enabled) return false;
    if (a.isSystem) return true;
    if (enabledAgentNames.length === 0) return true;
    return enabledAgentNames.includes(a.name);
  });

  const handleTextChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      setContent(value);

      const cursorPos = e.target.selectionStart ?? value.length;

      // Find the last @ before cursor that is preceded by start-of-input or whitespace
      let atIndex = -1;
      for (let i = cursorPos - 1; i >= 0; i--) {
        if (value[i] === "@") {
          if (i === 0 || /\s/.test(value[i - 1])) {
            atIndex = i;
          }
          break;
        }
        // If we hit whitespace before finding @, no active mention
        if (/\s/.test(value[i])) break;
      }

      if (atIndex >= 0) {
        const query = value.slice(atIndex + 1, cursorPos);
        // Close if query contains invalid chars
        if (/[^a-zA-Z0-9_-]/.test(query)) {
          setMentionQuery(null);
        } else {
          setMentionStartIndex(atIndex);
          setMentionQuery(query);
        }
      } else {
        setMentionQuery(null);
      }
    },
    []
  );

  const handleMentionSelect = useCallback(
    (agentName: string) => {
      const before = content.slice(0, mentionStartIndex);
      const after = content.slice(
        mentionStartIndex +
          1 +
          (mentionQuery?.length ?? 0)
      );
      const newContent = `${before}@${agentName} ${after}`;
      setContent(newContent);
      setSelectedAgent(agentName);
      setMentionQuery(null);

      // Restore focus and set cursor position after the inserted mention
      requestAnimationFrame(() => {
        const el = textareaRef.current;
        if (el) {
          el.focus();
          const pos = before.length + 1 + agentName.length + 1; // @name + space
          el.selectionStart = pos;
          el.selectionEnd = pos;
        }
      });
    },
    [content, mentionStartIndex, mentionQuery]
  );

  const handleSend = async () => {
    const trimmed = content.trim();
    if (!trimmed) return;

    // Parse @mentions: use the last mentioned agent name if it matches a known agent
    let agentForSubmit = selectedAgent;
    const mentionMatches = trimmed.match(/@(\w[\w-]*)/g);
    if (mentionMatches && filteredAgents) {
      const lastMention = mentionMatches[mentionMatches.length - 1].slice(1); // remove @
      if (filteredAgents.some((a) => a.name === lastMention)) {
        agentForSubmit = lastMention;
        setSelectedAgent(lastMention);
      }
    }

    if (!isPlanChatMode && !agentForSubmit) return;
    setIsSubmitting(true);
    setError("");
    try {
      if (isPlanChatMode) {
        // Plan-chat: just post the message, Lead Agent subscription handles it
        await postPlanMessage({ taskId: task._id, content: trimmed });
      } else {
        await sendMessage({
          taskId: task._id,
          content: trimmed,
          agentName: agentForSubmit,
        });
      }
      setContent("");
      onMessageSent?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Intercept keys when autocomplete is open
    if (mentionQuery !== null) {
      const nav = (textareaRef.current as any)?.__mentionNav;
      if (nav) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          e.stopPropagation();
          nav.navigateDown();
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          e.stopPropagation();
          nav.navigateUp();
          return;
        }
        if (e.key === "Enter" || e.key === "Tab") {
          e.preventDefault();
          e.stopPropagation();
          nav.selectFocused();
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          nav.close();
          return;
        }
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) handleSend();
    }
  };

  const handleRestore = async () => {
    setIsRestoring(true);
    setError("");
    try {
      await restoreTask({ taskId: task._id, mode: "previous" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore task.");
    } finally {
      setIsRestoring(false);
    }
  };

  if (task.status === "deleted") {
    return (
      <div className="px-6 py-3 border-t space-y-2">
        {error && <p className="text-xs text-red-500">{error}</p>}
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Task is in trash. Restore to send a message?
          </p>
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-7"
            onClick={handleRestore}
            disabled={isRestoring}
          >
            <RotateCcw className="h-3 w-3 mr-1.5" />
            {isRestoring ? "Restoring..." : "Restore"}
          </Button>
        </div>
      </div>
    );
  }

  if (isBlocked) {
    return (
      <div className="px-6 py-3 border-t bg-muted/30">
        <p className="text-xs text-muted-foreground text-center">
          Agent is currently working...
        </p>
      </div>
    );
  }

  // Plan-chat mode: simplified input addressed to the Lead Agent
  if (isPlanChatMode) {
    return (
      <div className="px-6 py-3 border-t space-y-2">
        {error && (
          <p className="text-xs text-red-500">{error}</p>
        )}
        <p className="text-xs text-muted-foreground">
          Ask the Lead Agent to modify the plan...
        </p>
        <div className="flex gap-2">
          <Textarea
            placeholder="e.g. Add a step to write tests, or remove the deployment step..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            className="text-sm min-h-[80px] max-h-[160px] resize-none"
            disabled={isSubmitting}
          />
          <Button
            size="icon"
            variant="default"
            className="h-[80px] w-10 shrink-0"
            onClick={handleSend}
            disabled={!canSend}
          >
            <SendHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="px-6 py-3 border-t space-y-2">
      {error && (
        <p className="text-xs text-red-500">{error}</p>
      )}
      <div className="flex items-center gap-2">
        <Select value={selectedAgent} onValueChange={setSelectedAgent}>
          <SelectTrigger className="w-[180px] h-7 text-xs">
            <SelectValue placeholder="Select agent" />
          </SelectTrigger>
          <SelectContent>
            {filteredAgents?.map((agent) => (
              <SelectItem key={agent._id} value={agent.name} className="text-xs">
                {agent.displayName || agent.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex gap-2 relative">
        <Textarea
          ref={textareaRef}
          placeholder="Send a message to the agent..."
          value={content}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            // Delay close to allow click on autocomplete portal
            setTimeout(() => setMentionQuery(null), 150);
          }}
          className="text-sm min-h-[80px] max-h-[160px] resize-none"
          disabled={isSubmitting}
        />
        <Button
          size="icon"
          variant="default"
          className="h-[80px] w-10 shrink-0"
          onClick={handleSend}
          disabled={!canSend}
        >
          <SendHorizontal className="h-4 w-4" />
        </Button>
        {mentionQuery !== null && !isPlanChatMode && filteredAgents && (
          <AgentMentionAutocomplete
            agents={filteredAgents.map((a) => ({
              name: a.name,
              displayName: a.displayName ?? undefined,
              role: a.role ?? undefined,
            }))}
            query={mentionQuery}
            onSelect={handleMentionSelect}
            onClose={() => setMentionQuery(null)}
            anchorRef={textareaRef}
          />
        )}
      </div>
    </div>
  );
}

"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";
import { useSelectableAgents } from "@/hooks/useSelectableAgents";

// Statuses where the user cannot interact with the task thread at all.
const BLOCKED_STATUSES = ["retrying"];

/** Imperative navigation API attached to textarea by AgentMentionAutocomplete */
interface MentionNavElement {
  navigateDown: () => void;
  navigateUp: () => void;
  selectFocused: () => boolean | void;
  close: () => void;
}

export interface ThreadComposerState {
  content: string;
  setContent: (value: string) => void;
  selectedAgent: string;
  setSelectedAgent: (agent: string) => void;
  inputMode: "agent" | "comment";
  setInputMode: (mode: "agent" | "comment") => void;
  isSubmitting: boolean;
  isRestoring: boolean;
  error: string;
  mentionQuery: string | null;
  mentionStartIndex: number;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  canSend: boolean;
  isPlanChatMode: boolean;
  isInProgress: boolean;
  isBlocked: boolean;
  filteredAgents: Doc<"agents">[] | undefined;
  handleTextChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  handleMentionSelect: (agentName: string) => void;
  handleSend: () => Promise<void>;
  handleKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  handleRestore: () => Promise<void>;
}

/**
 * Extracts all thread composer logic (draft state, send, mention detection)
 * from TaskDetailSheet / ThreadInput into a reusable hook.
 */
export function useThreadComposer(task: Doc<"tasks"> | null): ThreadComposerState {
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [error, setError] = useState("");
  const [selectedAgent, setSelectedAgent] = useState(task?.assignedAgent ?? "");
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [mentionStartIndex, setMentionStartIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const contentRef = useRef(content);
  const mentionStartIndexRef = useRef(mentionStartIndex);
  const mentionQueryRef = useRef(mentionQuery);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [inputMode, setInputMode] = useState<"agent" | "comment">("agent");

  const sendMessage = useMutation(api.messages.sendThreadMessage);
  const postPlanMessage = useMutation(api.messages.postUserPlanMessage);
  const postComment = useMutation(api.messages.postComment);
  const restoreTask = useMutation(api.tasks.restore);
  const board = useQuery(api.boards.getById, task?.boardId ? { boardId: task.boardId } : "skip");

  // Keep refs in sync with state for stable closures
  useEffect(() => {
    contentRef.current = content;
  }, [content]);
  useEffect(() => {
    mentionStartIndexRef.current = mentionStartIndex;
  }, [mentionStartIndex]);
  useEffect(() => {
    mentionQueryRef.current = mentionQuery;
  }, [mentionQuery]);
  useEffect(() => () => clearTimeout(blurTimeoutRef.current), []);

  // Sync selectedAgent when task.assignedAgent changes
  useEffect(() => {
    if (task?.assignedAgent && !isSubmitting) {
      setSelectedAgent(task.assignedAgent);
    }
  }, [task?.assignedAgent, isSubmitting]);

  const awaitingKickoff = task
    ? (task as Doc<"tasks"> & { awaitingKickoff?: boolean }).awaitingKickoff
    : undefined;
  const isPlanChatMode = task?.status === "review" && awaitingKickoff === true;
  const isInProgress =
    task?.status === "in_progress" || (task?.status === "review" && awaitingKickoff !== true);
  const isBlocked = task ? BLOCKED_STATUSES.includes(task.status) : false;

  const canSend =
    content.trim().length > 0 &&
    !isSubmitting &&
    (inputMode === "comment" || isPlanChatMode || isInProgress || !!selectedAgent);

  const filteredAgents = useSelectableAgents(board?.enabledAgents);

  const handleTextChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setContent(value);

    const cursorPos = e.target.selectionStart ?? value.length;

    let atIndex = -1;
    for (let i = cursorPos - 1; i >= 0; i--) {
      if (value[i] === "@") {
        if (i === 0 || /\s/.test(value[i - 1])) {
          atIndex = i;
        }
        break;
      }
      if (/\s/.test(value[i])) break;
    }

    if (atIndex >= 0) {
      const query = value.slice(atIndex + 1, cursorPos);
      if (/[^a-zA-Z0-9_-]/.test(query)) {
        setMentionQuery(null);
      } else {
        setMentionStartIndex(atIndex);
        setMentionQuery(query);
      }
    } else {
      setMentionQuery(null);
    }
  }, []);

  const handleMentionSelect = useCallback((agentName: string) => {
    const currentContent = contentRef.current;
    const startIdx = mentionStartIndexRef.current;
    const mQuery = mentionQueryRef.current;
    const before = currentContent.slice(0, startIdx);
    const after = currentContent.slice(startIdx + 1 + (mQuery?.length ?? 0));
    const newContent = `${before}@${agentName} ${after}`;
    setContent(newContent);
    setSelectedAgent(agentName);
    setMentionQuery(null);

    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (el) {
        el.focus();
        const pos = before.length + 1 + agentName.length + 1;
        el.selectionStart = pos;
        el.selectionEnd = pos;
      }
    });
  }, []);

  const handleSend = useCallback(async () => {
    if (!task) return;
    const trimmed = content.trim();
    if (!trimmed) return;

    let agentForSubmit = selectedAgent;
    const mentionMatches = trimmed.match(/@(\w[\w-]*)/g);
    if (mentionMatches && filteredAgents) {
      const lastMention = mentionMatches[mentionMatches.length - 1].slice(1);
      if (filteredAgents.some((a) => a.name === lastMention)) {
        agentForSubmit = lastMention;
        setSelectedAgent(lastMention);
      }
    }

    if (inputMode !== "comment" && !isPlanChatMode && !isInProgress && !agentForSubmit) return;
    setIsSubmitting(true);
    setError("");
    try {
      if (inputMode === "comment") {
        await postComment({ taskId: task._id, content: trimmed });
      } else if (isPlanChatMode || isInProgress) {
        await postPlanMessage({ taskId: task._id, content: trimmed });
      } else {
        await sendMessage({
          taskId: task._id,
          content: trimmed,
          agentName: agentForSubmit,
        });
      }
      setContent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }, [
    task,
    content,
    selectedAgent,
    inputMode,
    isPlanChatMode,
    isInProgress,
    filteredAgents,
    postComment,
    postPlanMessage,
    sendMessage,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (mentionQuery !== null) {
        const nav = (
          textareaRef.current as (HTMLTextAreaElement & { __mentionNav?: MentionNavElement }) | null
        )?.__mentionNav;
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
            const selected = nav.selectFocused();
            if (selected !== false) {
              e.preventDefault();
              e.stopPropagation();
            }
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
    },
    [mentionQuery, canSend, handleSend],
  );

  const handleRestore = useCallback(async () => {
    if (!task) return;
    setIsRestoring(true);
    setError("");
    try {
      await restoreTask({ taskId: task._id, mode: "previous" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore task.");
    } finally {
      setIsRestoring(false);
    }
  }, [task, restoreTask]);

  return {
    content,
    setContent,
    selectedAgent,
    setSelectedAgent,
    inputMode,
    setInputMode,
    isSubmitting,
    isRestoring,
    error,
    mentionQuery,
    mentionStartIndex,
    textareaRef,
    canSend,
    isPlanChatMode,
    isInProgress,
    isBlocked,
    filteredAgents,
    handleTextChange,
    handleMentionSelect,
    handleSend,
    handleKeyDown,
    handleRestore,
  };
}

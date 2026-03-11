"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";
import { useFileUpload } from "@/hooks/useFileUpload";
import { useSelectableAgents } from "@/hooks/useSelectableAgents";

const BLOCKED_STATUSES = ["retrying"];

export interface ThreadInputController {
  canSend: boolean;
  closeMentionAutocomplete: () => void;
  content: string;
  error: string;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  fileUploadError: string;
  filteredAgents: Doc<"agents">[] | undefined;
  handleDragLeave: (event: React.DragEvent) => void;
  handleDragOver: (event: React.DragEvent) => void;
  handleDrop: (event: React.DragEvent) => void;
  handleFileInputChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  handleMentionSelect: (agentName: string) => void;
  handleRestore: () => Promise<void>;
  handleSend: () => Promise<void>;
  handleTextBlur: () => void;
  handleTextChange: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  handleTextFocus: () => void;
  inputMode: "agent" | "comment";
  isBlocked: boolean;
  isHumanDelegationThread: boolean;
  isLeadAgentMode: boolean;
  isDragOver: boolean;
  isInProgress: boolean;
  isPlanChatMode: boolean;
  isReplyOnlyThread: boolean;
  isRestoring: boolean;
  isSubmitting: boolean;
  isUploading: boolean;
  mentionQuery: string | null;
  onDirectContentChange: (value: string) => void;
  openFilePicker: () => void;
  pendingFiles: Array<{ name: string; size: number; type: string }>;
  removePendingFile: (name: string) => void;
  selectedAgent: string;
  setInputMode: (mode: "agent" | "comment") => void;
  setSelectedAgent: (agentName: string) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

interface UseThreadInputControllerArgs {
  mode?: "default" | "lead-agent";
  task: Doc<"tasks">;
  onMessageSent?: () => void;
}

export function useThreadInputController({
  mode = "default",
  task,
  onMessageSent,
}: UseThreadInputControllerArgs): ThreadInputController {
  const initialSelectedAgent = task.assignedAgent === "human" ? "" : (task.assignedAgent ?? "");
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [error, setError] = useState("");
  const [selectedAgent, setSelectedAgent] = useState(initialSelectedAgent);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [mentionStartIndex, setMentionStartIndex] = useState(0);
  const [inputMode, setInputMode] = useState<"agent" | "comment">("agent");
  const [isDragOver, setIsDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const contentRef = useRef(content);
  const mentionStartIndexRef = useRef(mentionStartIndex);
  const mentionQueryRef = useRef(mentionQuery);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const sendMessage = useMutation(api.messages.sendThreadMessage);
  const postPlanMessage = useMutation(api.messages.postUserPlanMessage);
  const postComment = useMutation(api.messages.postComment);
  const postMentionMessage = useMutation(api.messages.postMentionMessage);
  const restoreTask = useMutation(api.tasks.restore);
  const board = useQuery(api.boards.getById, task.boardId ? { boardId: task.boardId } : "skip");

  const {
    pendingFiles,
    isUploading,
    uploadError: fileUploadError,
    fileInputRef,
    addFiles,
    removePendingFile,
    uploadAll,
    openFilePicker,
    clearPending,
  } = useFileUpload(task._id);

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

  useEffect(() => {
    if (!isSubmitting) {
      setSelectedAgent(task.assignedAgent === "human" ? "" : (task.assignedAgent ?? ""));
    }
  }, [task.assignedAgent, isSubmitting]);

  const isLeadAgentMode = mode === "lead-agent";
  const isPlanChatMode = isLeadAgentMode;
  const isInProgress = task.status === "in_progress";
  const isHumanDelegationThread = task.assignedAgent === "human";
  const isReplyOnlyThread = isInProgress && !isHumanDelegationThread;
  const isBlocked = BLOCKED_STATUSES.includes(task.status);
  const filteredAgents = useSelectableAgents(board?.enabledAgents);

  const { hasMention, firstMentionedAgentName } = useMemo(() => {
    if (isLeadAgentMode) {
      return {
        firstMentionedAgentName: undefined as string | undefined,
        hasMention: false,
      };
    }
    const matches = content.match(/@(\w[\w-]*)/g);
    if (!matches || !filteredAgents) {
      return {
        firstMentionedAgentName: undefined as string | undefined,
        hasMention: false,
      };
    }

    for (const match of matches) {
      const name = match.slice(1);
      if (filteredAgents.some((agent) => agent.name === name)) {
        return { firstMentionedAgentName: name, hasMention: true };
      }
    }

    return {
      firstMentionedAgentName: undefined as string | undefined,
      hasMention: false,
    };
  }, [content, filteredAgents, isLeadAgentMode]);

  const canSend =
    (content.trim().length > 0 || pendingFiles.length > 0) &&
    !isSubmitting &&
    !isUploading &&
    (
      inputMode === "comment"
      || isPlanChatMode
      || isReplyOnlyThread
      || !!selectedAgent
      || hasMention
    );

  const handleTextChange = useCallback((event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = event.target.value;
    setContent(value);

    const cursorPos = event.target.selectionStart ?? value.length;
    let atIndex = -1;
    for (let i = cursorPos - 1; i >= 0; i -= 1) {
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
    const currentMentionQuery = mentionQueryRef.current;
    const before = currentContent.slice(0, startIdx);
    const after = currentContent.slice(startIdx + 1 + (currentMentionQuery?.length ?? 0));
    const nextContent = `${before}@${agentName} ${after}`;
    setContent(nextContent);
    setSelectedAgent(agentName);
    setMentionQuery(null);

    requestAnimationFrame(() => {
      const element = textareaRef.current;
      if (!element) return;

      element.focus();
      const position = before.length + 1 + agentName.length + 1;
      element.selectionStart = position;
      element.selectionEnd = position;
    });
  }, []);

  const handleSend = useCallback(async () => {
    const trimmed = content.trim();
    if (!trimmed && pendingFiles.length === 0) return;

    const agentForSubmit = firstMentionedAgentName ?? selectedAgent;
    if (firstMentionedAgentName) {
      setSelectedAgent(firstMentionedAgentName);
    }

    if (
      inputMode !== "comment" &&
      !isPlanChatMode &&
      !isReplyOnlyThread &&
      !hasMention &&
      !agentForSubmit
    ) {
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      let fileAttachments: Array<{ name: string; size: number; type: string }> | undefined;

      if (pendingFiles.length > 0) {
        const uploaded = await uploadAll();
        fileAttachments = uploaded.map((file) => ({
          name: file.name,
          size: file.size,
          type: file.type,
        }));
      }

      const messageContent = trimmed || "(files attached)";

      if (inputMode === "comment") {
        await postComment({
          content: messageContent,
          fileAttachments,
          taskId: task._id,
        });
      } else if (isPlanChatMode || isReplyOnlyThread) {
        await postPlanMessage({
          content: messageContent,
          fileAttachments,
          taskId: task._id,
        });
      } else if (hasMention && firstMentionedAgentName) {
        await postMentionMessage({
          content: messageContent,
          fileAttachments,
          mentionedAgent: firstMentionedAgentName,
          taskId: task._id,
        });
      } else {
        await sendMessage({
          agentName: agentForSubmit,
          content: messageContent,
          fileAttachments,
          taskId: task._id,
        });
      }

      setContent("");
      clearPending();
      onMessageSent?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }, [
    clearPending,
    content,
    firstMentionedAgentName,
    hasMention,
    inputMode,
    isLeadAgentMode,
    isPlanChatMode,
    isReplyOnlyThread,
    onMessageSent,
    pendingFiles.length,
    postComment,
    postMentionMessage,
    postPlanMessage,
    selectedAgent,
    sendMessage,
    task._id,
    uploadAll,
  ]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (mentionQuery !== null) {
        const nav = (
          textareaRef.current as
            | (HTMLTextAreaElement & {
                __mentionNav?: {
                  close: () => void;
                  navigateDown: () => void;
                  navigateUp: () => void;
                  selectFocused: () => boolean | void;
                };
              })
            | null
        )?.__mentionNav;

        if (nav) {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            event.stopPropagation();
            nav.navigateDown();
            return;
          }

          if (event.key === "ArrowUp") {
            event.preventDefault();
            event.stopPropagation();
            nav.navigateUp();
            return;
          }

          if (event.key === "Enter" || event.key === "Tab") {
            const selected = nav.selectFocused();
            if (selected !== false) {
              event.preventDefault();
              event.stopPropagation();
            }
            return;
          }

          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            nav.close();
            return;
          }
        }
      }

      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (canSend) {
          void handleSend();
        }
      }
    },
    [canSend, handleSend, mentionQuery],
  );

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      event.stopPropagation();
      setIsDragOver(false);
      if (event.dataTransfer.files.length > 0) {
        addFiles(event.dataTransfer.files);
      }
    },
    [addFiles],
  );

  const handleFileInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files;
      if (files && files.length > 0) {
        addFiles(files);
      }
      event.target.value = "";
    },
    [addFiles],
  );

  const handleRestore = useCallback(async () => {
    setIsRestoring(true);
    setError("");
    try {
      await restoreTask({ mode: "previous", taskId: task._id });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore task.");
    } finally {
      setIsRestoring(false);
    }
  }, [restoreTask, task._id]);

  const onDirectContentChange = useCallback((value: string) => {
    setContent(value);
  }, []);

  const handleTextFocus = useCallback(() => {
    clearTimeout(blurTimeoutRef.current);
  }, []);

  const handleTextBlur = useCallback(() => {
    blurTimeoutRef.current = setTimeout(() => setMentionQuery(null), 150);
  }, []);

  const closeMentionAutocomplete = useCallback(() => {
    setMentionQuery(null);
  }, []);

  return {
    canSend,
    closeMentionAutocomplete,
    content,
    error,
    fileInputRef,
    fileUploadError,
    filteredAgents,
    handleDragLeave,
    handleDragOver,
    handleDrop,
    handleFileInputChange,
    handleKeyDown,
    handleMentionSelect,
    handleRestore,
    handleSend,
    handleTextBlur,
    handleTextChange,
    handleTextFocus,
    inputMode,
    isBlocked,
    isHumanDelegationThread,
    isLeadAgentMode,
    isDragOver,
    isInProgress,
    isPlanChatMode,
    isReplyOnlyThread,
    isRestoring,
    isSubmitting,
    isUploading,
    mentionQuery,
    onDirectContentChange,
    openFilePicker,
    pendingFiles,
    removePendingFile,
    selectedAgent,
    setInputMode,
    setSelectedAgent,
    textareaRef,
  };
}

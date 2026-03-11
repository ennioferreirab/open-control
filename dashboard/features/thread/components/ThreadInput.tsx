"use client";

import { Loader2, MessageCircle, Paperclip, RotateCcw, SendHorizontal } from "lucide-react";
import type { Doc } from "@/convex/_generated/dataModel";
import { AgentMentionAutocomplete } from "@/components/AgentMentionAutocomplete";
import { FileChip } from "@/components/FileChip";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useThreadInputController } from "@/hooks/useThreadInputController";

interface ThreadInputProps {
  mode?: "default" | "lead-agent";
  task: Doc<"tasks">;
  onMessageSent?: () => void;
}

export function ThreadInput({ task, onMessageSent, mode = "default" }: ThreadInputProps) {
  const {
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
  } = useThreadInputController({ mode, onMessageSent, task });

  const modePill = (primaryLabel: string) => (
    <div className="inline-flex rounded-full bg-muted p-0.5 text-xs">
      <button
        type="button"
        className={`rounded-full px-3 py-1 transition-colors ${
          inputMode === "agent"
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        }`}
        onClick={() => setInputMode("agent")}
      >
        {primaryLabel}
      </button>
      <button
        type="button"
        className={`rounded-full px-3 py-1 transition-colors flex items-center gap-1 ${
          inputMode === "comment"
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        }`}
        onClick={() => setInputMode("comment")}
      >
        <MessageCircle className="h-3 w-3" />
        Comment
      </button>
    </div>
  );
  const shellClass = "mx-auto w-full min-w-0 max-w-5xl";

  if (task.status === "deleted") {
    return (
      <div className="border-t px-6 py-3">
        <div className={`${shellClass} space-y-2`}>
          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              Task is in trash. Restore to send a message?
            </p>
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-7"
              onClick={() => void handleRestore()}
              disabled={isRestoring}
            >
              <RotateCcw className="h-3 w-3 mr-1.5" />
              {isRestoring ? "Restoring..." : "Restore"}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (isBlocked) {
    return (
      <div className="border-t bg-muted/30 px-6 py-3">
        <div className={shellClass}>
          <p className="text-center text-xs text-muted-foreground">Agent is currently working...</p>
        </div>
      </div>
    );
  }

  if (isPlanChatMode) {
    return (
      <div className="border-t px-6 py-3">
        <div className={`${shellClass} space-y-2`}>
          {error && <p className="text-xs text-red-500">{error}</p>}
          {isLeadAgentMode ? (
            <>
              <div className="flex items-center gap-2">
                <span className="inline-flex rounded-full bg-muted px-3 py-1 text-xs font-medium">
                  Lead Agent
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Send changes directly to the Lead Agent. Mentions and delegation are disabled here.
              </p>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2">{modePill("Plan Chat")}</div>
              {inputMode === "comment" ? (
                <p className="text-xs text-muted-foreground">
                  Add a note without triggering agents...
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Ask the Lead Agent to modify the plan...
                </p>
              )}
            </>
          )}
          {fileUploadError && <p className="text-xs text-red-500">{fileUploadError}</p>}
          {pendingFiles.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {pendingFiles.map((pendingFile) => (
                <FileChip
                  key={pendingFile.name}
                  name={pendingFile.name}
                  size={pendingFile.size}
                  onRemove={() => removePendingFile(pendingFile.name)}
                />
              ))}
            </div>
          )}
          <div
            className={`flex gap-2 ${isDragOver ? "ring-2 ring-primary ring-offset-1 rounded-md" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <Textarea
              placeholder={
                isLeadAgentMode
                  ? "Ask the Lead Agent to change the plan..."
                  : inputMode === "comment"
                    ? "Add a comment..."
                    : "e.g. Add a step to write tests, or remove the deployment step..."
              }
              value={content}
              onChange={(event) => onDirectContentChange(event.target.value)}
              onKeyDown={handleKeyDown}
              className="text-sm min-h-[80px] max-h-[160px] resize-none"
              disabled={isSubmitting}
            />
            <div className="flex flex-col gap-1 shrink-0">
              <Button
                size="icon"
                variant="default"
                className="h-[38px] w-10"
                onClick={() => void handleSend()}
                disabled={!canSend}
              >
                <SendHorizontal className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-[38px] w-10"
                onClick={openFilePicker}
                disabled={isSubmitting || isUploading}
                title="Attach files"
              >
                {isUploading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Paperclip className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileInputChange}
            aria-label="Attach files to message"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="border-t px-6 py-3">
      <div className={`${shellClass} space-y-2`}>
        {error && <p className="text-xs text-red-500">{error}</p>}
        <div className="flex items-center gap-2">
          {modePill(isReplyOnlyThread ? "Reply" : "Message Agent")}
          {inputMode === "agent" && !isReplyOnlyThread && (
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
          )}
        </div>
        {fileUploadError && <p className="text-xs text-red-500">{fileUploadError}</p>}
        {pendingFiles.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {pendingFiles.map((pendingFile) => (
              <FileChip
                key={pendingFile.name}
                name={pendingFile.name}
                size={pendingFile.size}
                onRemove={() => removePendingFile(pendingFile.name)}
              />
            ))}
          </div>
        )}
        <div
          className={`relative flex gap-2 ${isDragOver ? "ring-2 ring-primary ring-offset-1 rounded-md" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <Textarea
            ref={textareaRef}
            placeholder={
              inputMode === "comment"
                ? "Add a comment..."
                : isReplyOnlyThread
                  ? "Reply to the thread..."
                  : "Send a message to the agent..."
            }
            value={content}
            onChange={
              inputMode === "comment"
                ? (event) => onDirectContentChange(event.target.value)
                : handleTextChange
            }
            onKeyDown={handleKeyDown}
            onFocus={handleTextFocus}
            onBlur={handleTextBlur}
            className="text-sm min-h-[80px] max-h-[160px] resize-none"
            disabled={isSubmitting}
          />
          <div className="flex flex-col gap-1 shrink-0">
            <Button
              size="icon"
              variant="default"
              className="h-[38px] w-10"
              onClick={() => void handleSend()}
              disabled={!canSend}
            >
              <SendHorizontal className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-[38px] w-10"
              onClick={openFilePicker}
              disabled={isSubmitting || isUploading}
              title="Attach files"
            >
              {isUploading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Paperclip className="h-4 w-4" />
              )}
            </Button>
          </div>
          {inputMode === "agent" &&
            mentionQuery !== null &&
            !isPlanChatMode &&
            !isReplyOnlyThread &&
            filteredAgents && (
              <AgentMentionAutocomplete
                agents={filteredAgents.map((agent) => ({
                  displayName: agent.displayName ?? undefined,
                  name: agent.name,
                  role: agent.role ?? undefined,
                }))}
                query={mentionQuery}
                onSelect={handleMentionSelect}
                onClose={closeMentionAutocomplete}
                anchorRef={textareaRef}
              />
            )}
        </div>
        {isHumanDelegationThread && (
          <p className="text-xs text-muted-foreground">
            This thread is waiting on a human. Pick an agent or use <code>@mention</code> to hand it
            back off.
          </p>
        )}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileInputChange}
          aria-label="Attach files to message"
        />
      </div>
    </div>
  );
}

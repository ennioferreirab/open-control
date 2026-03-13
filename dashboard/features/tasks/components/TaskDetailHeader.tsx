"use client";

import { Fragment, type KeyboardEvent } from "react";
import type { Doc } from "@/convex/_generated/dataModel";
import { SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Pause, Pencil, Play, Trash2 } from "lucide-react";
import { TAG_COLORS } from "@/lib/constants";
import type { MergedTaskRef, TaskDetailViewData } from "@/features/tasks/hooks/useTaskDetailView";
import { InlineRejection } from "@/components/InlineRejection";

type HeaderStatusColors = NonNullable<TaskDetailViewData["colors"]>;

type ManualPrimaryAction = {
  label: string;
  pendingLabel: string;
  onClick: () => void | Promise<void>;
  testId: string;
  isPending: boolean;
} | null;

interface TaskDetailHeaderProps {
  task: Doc<"tasks">;
  taskId: TaskDetailViewData["task"] extends Doc<"tasks"> | null ? Doc<"tasks">["_id"] : never;
  colors: HeaderStatusColors | null;
  taskStatus: string | undefined;
  isAwaitingKickoff: boolean;
  isPaused: boolean;
  isMergeLockedSource: boolean;
  mergedIntoTask: MergedTaskRef | null | undefined;
  tagColorMap: Record<string, string>;
  tagAttributesList: TaskDetailViewData["tagAttributesList"];
  tagAttrValues: TaskDetailViewData["tagAttrValues"];
  localPlanExists: boolean;
  taskExecutionPlanExists: boolean;
  showRejection: boolean;
  showDeleteConfirm: boolean;
  deleteTaskError: string;
  isDeletingTask: boolean;
  kickOffError: string;
  clearPlanError: string;
  pauseError: string;
  resumeError: string;
  savePlanError: string;
  startInboxError: string;
  isSavingPlan: boolean;
  isStartingInbox: boolean;
  isPausing: boolean;
  isResuming: boolean;
  liveSessionLabel: string | null;
  isEditingTitle: boolean;
  editTitleValue: string;
  isEditingDescription: boolean;
  editDescriptionValue: string;
  manualPlanPrimaryAction: ManualPrimaryAction;
  onApprove: () => void;
  onRetry: () => void | Promise<void>;
  onPause: () => void | Promise<void>;
  onResume: () => void | Promise<void>;
  onSavePlan: () => void | Promise<void>;
  onStartInbox: () => void | Promise<void>;
  onDeleteTask: () => void | Promise<void>;
  onOpenLive?: (() => void) | null;
  onOpenMergedTask: (taskId: Doc<"tasks">["_id"]) => void;
  onToggleRejection: () => void;
  onDeleteConfirmOpen: () => void;
  onDeleteConfirmClose: () => void;
  onStartEditingTitle: () => void;
  onTitleValueChange: (value: string) => void;
  onSaveTitle: () => void | Promise<void>;
  onCancelEditingTitle: () => void;
  onStartEditingDescription: () => void;
  onDescriptionValueChange: (value: string) => void;
  onSaveDescription: () => void | Promise<void>;
  onCancelEditingDescription: () => void;
}

function renderTitleKeyDown(
  event: KeyboardEvent<HTMLInputElement>,
  onSaveTitle: () => void | Promise<void>,
  onCancelEditingTitle: () => void,
): void {
  if (event.key === "Enter") {
    event.preventDefault();
    void onSaveTitle();
  }

  if (event.key === "Escape") {
    onCancelEditingTitle();
  }
}

function renderDescriptionKeyDown(
  event: KeyboardEvent<HTMLTextAreaElement>,
  onCancelEditingDescription: () => void,
): void {
  if (event.key === "Escape") {
    onCancelEditingDescription();
  }
}

export function TaskDetailHeader({
  task,
  taskId,
  colors,
  taskStatus,
  isAwaitingKickoff,
  isPaused,
  isMergeLockedSource,
  mergedIntoTask,
  tagColorMap,
  tagAttributesList,
  tagAttrValues,
  localPlanExists,
  taskExecutionPlanExists,
  showRejection,
  showDeleteConfirm,
  deleteTaskError,
  isDeletingTask,
  kickOffError,
  clearPlanError,
  pauseError,
  resumeError,
  savePlanError,
  startInboxError,
  isSavingPlan,
  isStartingInbox,
  isPausing,
  isResuming,
  liveSessionLabel,
  isEditingTitle,
  editTitleValue,
  isEditingDescription,
  editDescriptionValue,
  manualPlanPrimaryAction,
  onApprove,
  onRetry,
  onPause,
  onResume,
  onSavePlan,
  onStartInbox,
  onDeleteTask,
  onOpenLive,
  onOpenMergedTask,
  onToggleRejection,
  onDeleteConfirmOpen,
  onDeleteConfirmClose,
  onStartEditingTitle,
  onTitleValueChange,
  onSaveTitle,
  onCancelEditingTitle,
  onStartEditingDescription,
  onDescriptionValueChange,
  onSaveDescription,
  onCancelEditingDescription,
}: TaskDetailHeaderProps) {
  return (
    <SheetHeader className="px-6 pt-6 pb-4">
      <SheetTitle className="text-lg font-semibold pr-6">
        {isEditingTitle ? (
          <Input
            value={editTitleValue}
            onChange={(event) => onTitleValueChange(event.target.value)}
            onBlur={() => void onSaveTitle()}
            onKeyDown={(event) => renderTitleKeyDown(event, onSaveTitle, onCancelEditingTitle)}
            className="text-base font-semibold h-7 py-0 border-0 border-b rounded-none focus-visible:ring-0 px-0"
            autoFocus
          />
        ) : (
          <div className="flex items-start gap-1.5 group/title">
            <span className="flex-1">{task.title}</span>
            {!isMergeLockedSource && (
              <button
                type="button"
                onClick={onStartEditingTitle}
                className="opacity-0 group-hover/title:opacity-100 transition-opacity mt-0.5 flex-shrink-0 p-0.5 rounded hover:bg-accent"
                aria-label="Edit title"
              >
                <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            )}
          </div>
        )}
      </SheetTitle>
      <SheetDescription asChild>
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant="outline"
            className={`text-xs ${colors?.bg ?? "bg-muted"} ${colors?.text ?? "text-foreground"} border-0`}
          >
            {task.status.replaceAll("_", " ")}
          </Badge>
          {task.assignedAgent && (
            <span className="text-xs text-muted-foreground">{task.assignedAgent}</span>
          )}
          {(task.tags ?? []).map((tag) => {
            const colorKey = tagColorMap[tag];
            const color = colorKey ? TAG_COLORS[colorKey] : null;
            const chipClass = `inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs max-w-[200px] ${
              color ? `${color.bg} ${color.text}` : "bg-muted text-muted-foreground"
            }`;
            const renderDot = () =>
              color ? (
                <span className={`w-1.5 h-1.5 rounded-full ${color.dot} flex-shrink-0`} />
              ) : null;
            const attrs =
              tagAttrValues?.filter((value) => value.tagName === tag && value.value) ?? [];
            if (attrs.length === 0) {
              return (
                <span key={tag} className={chipClass} title={tag}>
                  {renderDot()}
                  <span className="truncate">{tag}</span>
                </span>
              );
            }
            return (
              <Fragment key={tag}>
                {attrs.map((attr) => {
                  const attrDef = tagAttributesList?.find(
                    (attribute) => attribute._id === attr.attributeId,
                  );
                  if (!attrDef) return null;
                  const label = `${tag}:${attrDef.name}=${attr.value}`;
                  return (
                    <span key={`${tag}-${attr.attributeId}`} className={chipClass} title={label}>
                      {renderDot()}
                      <span className="truncate">{label}</span>
                    </span>
                  );
                })}
              </Fragment>
            );
          })}
          {task.status === "review" && !task.isManual && !isAwaitingKickoff && (
            <>
              <Button
                variant="default"
                size="sm"
                className="bg-green-500 hover:bg-green-600 text-white text-xs h-7 px-2"
                onClick={onApprove}
              >
                Approve
              </Button>
              {task.trustLevel === "human_approved" && (
                <Button
                  variant="destructive"
                  size="sm"
                  className="text-xs h-7 px-2"
                  onClick={onToggleRejection}
                >
                  Deny
                </Button>
              )}
            </>
          )}
          {task.status === "crashed" && (
            <Button
              variant="outline"
              size="sm"
              className="border-amber-500 text-amber-700 hover:bg-amber-50 text-xs"
              onClick={() => void onRetry()}
            >
              Retry from Beginning
            </Button>
          )}
          {liveSessionLabel && (
            <>
              <Badge
                variant="outline"
                className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200"
                data-testid="live-session-badge"
              >
                {liveSessionLabel}
              </Badge>
              {onOpenLive && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs h-7 px-2"
                  onClick={() => void onOpenLive()}
                  data-testid="live-button"
                >
                  Live
                </Button>
              )}
            </>
          )}
          {task.status === "in_progress" && (
            <Button
              variant="outline"
              size="sm"
              className="border-orange-400 text-orange-700 hover:bg-orange-50 text-xs h-7 px-2"
              onClick={() => void onPause()}
              disabled={isPausing}
              data-testid="pause-button"
            >
              {isPausing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  Pausing...
                </>
              ) : (
                <>
                  <Pause className="h-3.5 w-3.5 mr-1" />
                  Pause
                </>
              )}
            </Button>
          )}
          {isPaused && !manualPlanPrimaryAction && (
            <>
              <Badge
                variant="outline"
                className="text-xs bg-orange-50 text-orange-700 border-orange-200"
                data-testid="paused-badge"
              >
                Paused
              </Badge>
              <Button
                variant="default"
                size="sm"
                className="bg-green-600 hover:bg-green-700 text-white text-xs h-7 px-2"
                onClick={() => void onResume()}
                disabled={isResuming}
                data-testid="resume-button"
              >
                {isResuming ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                    Resuming...
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5 mr-1" />
                    Resume
                  </>
                )}
              </Button>
            </>
          )}
          {isAwaitingKickoff && (
            <Badge
              variant="outline"
              className="text-xs bg-amber-50 text-amber-700 border-amber-200"
            >
              Awaiting Kick-off
            </Badge>
          )}
          {taskStatus === "inbox" && (
            <>
              {localPlanExists && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs h-7 px-2"
                  onClick={() => void onSavePlan()}
                  disabled={isSavingPlan}
                  data-testid="save-plan-button"
                >
                  {isSavingPlan ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save Plan"
                  )}
                </Button>
              )}
              {(localPlanExists || taskExecutionPlanExists) && (
                <Button
                  variant="default"
                  size="sm"
                  className="bg-green-600 hover:bg-green-700 text-white text-xs h-7 px-2"
                  onClick={() => void onStartInbox()}
                  disabled={isStartingInbox}
                  data-testid="start-inbox-button"
                >
                  {isStartingInbox ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                      Starting...
                    </>
                  ) : (
                    <>
                      <Play className="h-3.5 w-3.5 mr-1" />
                      Start
                    </>
                  )}
                </Button>
              )}
            </>
          )}
          {taskStatus === "review" && task.isManual && localPlanExists && (
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-7 px-2"
              onClick={() => void onSavePlan()}
              disabled={isSavingPlan}
              data-testid="save-plan-button"
            >
              {isSavingPlan ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Plan"
              )}
            </Button>
          )}
          {manualPlanPrimaryAction && (
            <Button
              variant="default"
              size="sm"
              className="bg-green-600 hover:bg-green-700 text-white text-xs h-7 px-2"
              onClick={() => void manualPlanPrimaryAction.onClick()}
              disabled={manualPlanPrimaryAction.isPending}
              data-testid={manualPlanPrimaryAction.testId}
            >
              {manualPlanPrimaryAction.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  {manualPlanPrimaryAction.pendingLabel}
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5 mr-1" />
                  {manualPlanPrimaryAction.label}
                </>
              )}
            </Button>
          )}
          {task.status !== "deleted" && !isMergeLockedSource && (
            <button
              type="button"
              onClick={onDeleteConfirmOpen}
              className="ml-auto flex-shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950 dark:hover:text-red-400"
              aria-label="Delete task"
              title="Delete task"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </SheetDescription>
      {showRejection && taskId && (
        <div className="pt-2">
          <InlineRejection taskId={taskId} onClose={onToggleRejection} />
        </div>
      )}
      {showDeleteConfirm && (
        <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 dark:border-red-800 dark:bg-red-950">
          <p className="text-xs text-red-800 dark:text-red-200 mb-2">
            Delete this task and all its steps?
          </p>
          {deleteTaskError && (
            <p className="text-xs text-red-600 dark:text-red-400 mb-2">{deleteTaskError}</p>
          )}
          <div className="flex items-center gap-2">
            <Button
              variant="destructive"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={() => void onDeleteTask()}
              disabled={isDeletingTask}
            >
              {isDeletingTask ? (
                <>
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Yes, delete"
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={onDeleteConfirmClose}
              disabled={isDeletingTask}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
      {isAwaitingKickoff && (
        <div
          className="mt-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800"
          data-testid="reviewing-plan-banner"
        >
          This task is awaiting your approval. Review the execution plan and respond in the Lead
          Agent panel below.
        </div>
      )}
      {kickOffError && (
        <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
          {kickOffError}
        </div>
      )}
      {clearPlanError && (
        <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
          {clearPlanError}
        </div>
      )}
      {pauseError && (
        <div
          className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800"
          data-testid="pause-error"
        >
          {pauseError}
        </div>
      )}
      {resumeError && (
        <div
          className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800"
          data-testid="resume-error"
        >
          {resumeError}
        </div>
      )}
      {savePlanError && (
        <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
          {savePlanError}
        </div>
      )}
      {startInboxError && (
        <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
          {startInboxError}
        </div>
      )}
      {isMergeLockedSource && mergedIntoTask && (
        <div className="mt-2 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-800">
          Merged into{" "}
          <button
            type="button"
            className="font-medium underline underline-offset-2"
            onClick={() => onOpenMergedTask(mergedIntoTask._id)}
          >
            {mergedIntoTask.title}
          </button>
          . Continue the thread and edits there.
        </div>
      )}
      <div className="mt-3 group/desc">
        {isEditingDescription ? (
          <textarea
            value={editDescriptionValue}
            onChange={(event) => onDescriptionValueChange(event.target.value)}
            onBlur={() => void onSaveDescription()}
            onKeyDown={(event) => renderDescriptionKeyDown(event, onCancelEditingDescription)}
            className="w-full text-sm text-foreground resize-none rounded-md border border-input bg-background px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring min-h-[60px]"
            placeholder="Describe this task..."
            autoFocus
            rows={3}
          />
        ) : (
          <div className="flex items-start gap-1.5">
            {task.description ? (
              <p className="text-sm text-muted-foreground flex-1 whitespace-pre-wrap">
                {task.description}
              </p>
            ) : (
              <p
                className="text-sm text-muted-foreground/50 italic flex-1 cursor-text"
                onClick={onStartEditingDescription}
              >
                Add description...
              </p>
            )}
            {!isMergeLockedSource && (
              <button
                type="button"
                onClick={onStartEditingDescription}
                className="opacity-0 group-hover/desc:opacity-100 transition-opacity mt-0.5 flex-shrink-0 p-0.5 rounded hover:bg-accent"
                aria-label="Edit description"
              >
                <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            )}
          </div>
        )}
      </div>
    </SheetHeader>
  );
}

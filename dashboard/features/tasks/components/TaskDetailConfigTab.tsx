"use client";

import type { Id, Doc } from "@/convex/_generated/dataModel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { TagAttributeEditor } from "@/components/TagAttributeEditor";
import { ChevronDown, ChevronRight, Loader2, Plus, X } from "lucide-react";
import { TAG_COLORS } from "@/lib/constants";
import type {
  MergeCandidateRef,
  MergeSourceRef,
  TaskDetailViewData,
} from "@/features/tasks/hooks/useTaskDetailView";

type TaskDetailTask = NonNullable<TaskDetailViewData["task"]>;

interface TaskDetailConfigTabProps {
  task: TaskDetailTask;
  directMergeSources: MergeSourceRef[] | undefined;
  canRemoveDirectSources: boolean;
  removeMergeSourceError: string;
  onTaskOpen?: (taskId: Id<"tasks">) => void;
  onRemoveMergeSource: (sourceTaskId: Id<"tasks">) => void | Promise<void>;
  isRemovingMergeSource: boolean;
  mergeQuery: string;
  onMergeQueryChange: (value: string) => void;
  isAddingMergeSource: boolean;
  mergeCandidates: MergeCandidateRef[] | undefined;
  selectedMergeTaskId: Id<"tasks"> | "";
  onSelectedMergeTaskIdChange: (taskId: Id<"tasks">) => void;
  onAddMergeSource: () => void | Promise<void>;
  addMergeSourceError: string;
  isMergeLockedSource: boolean;
  onCreateMergeTask: () => void | Promise<void>;
  isCreatingMergeTask: boolean;
  createMergeTaskError: string;
  tagColorMap: Record<string, string>;
  tagsList: Doc<"taskTags">[] | undefined;
  onAddTag: (tag: string) => void;
  onRemoveTag: (tag: string) => void;
  tagAttributesList: Doc<"tagAttributes">[] | undefined;
  tagAttrValues: Doc<"tagAttributeValues">[] | undefined;
  expandedTags: Set<string>;
  onToggleTagExpansion: (tag: string) => void;
}

export function TaskDetailConfigTab({
  task,
  directMergeSources,
  canRemoveDirectSources,
  removeMergeSourceError,
  onTaskOpen,
  onRemoveMergeSource,
  isRemovingMergeSource,
  mergeQuery,
  onMergeQueryChange,
  isAddingMergeSource,
  mergeCandidates,
  selectedMergeTaskId,
  onSelectedMergeTaskIdChange,
  onAddMergeSource,
  addMergeSourceError,
  isMergeLockedSource,
  onCreateMergeTask,
  isCreatingMergeTask,
  createMergeTaskError,
  tagColorMap,
  tagsList,
  onAddTag,
  onRemoveTag,
  tagAttributesList,
  tagAttrValues,
  expandedTags,
  onToggleTagExpansion,
}: TaskDetailConfigTabProps) {
  return (
    <div className="space-y-4" data-testid="config-content">
      {task.isMergeTask ? (
        <div className="space-y-4 rounded-md border border-border p-3">
          <div>
            <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Merge Sources
            </h4>
            <p className="mt-1 text-xs text-muted-foreground">
              Manage direct source tasks for this merged task. Source labels are recalculated
              automatically after changes.
            </p>
          </div>
          <div className="space-y-2">
            {(directMergeSources ?? []).map((source) => (
              <div key={source.taskId} className="flex items-center gap-2 text-sm text-foreground">
                <span className="min-w-0 flex-1">
                  {source.label}: {source.taskTitle}
                </span>
                <button
                  type="button"
                  className="text-xs text-sky-700 underline underline-offset-2"
                  onClick={() => onTaskOpen?.(source.taskId)}
                  aria-label={`Open merge source ${source.label}`}
                >
                  link
                </button>
                {canRemoveDirectSources && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => void onRemoveMergeSource(source.taskId)}
                    disabled={isRemovingMergeSource}
                    aria-label={`Remove merge source ${source.label}`}
                    className="h-7 px-2 text-destructive hover:text-destructive"
                  >
                    {isRemovingMergeSource ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <X className="h-3.5 w-3.5" />
                    )}
                  </Button>
                )}
              </div>
            ))}
          </div>
          {!canRemoveDirectSources && (
            <p className="text-xs text-muted-foreground">
              Merged tasks must keep at least 2 direct sources.
            </p>
          )}
          {removeMergeSourceError && (
            <p className="text-xs text-red-500">{removeMergeSourceError}</p>
          )}

          <Separator />

          <div className="space-y-2">
            <div>
              <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Attach Another Task
              </h4>
              <p className="mt-1 text-xs text-muted-foreground">
                Add another eligible task as a direct source of this merge.
              </p>
            </div>
            <Input
              value={mergeQuery}
              onChange={(event) => onMergeQueryChange(event.target.value)}
              placeholder="Search task to attach..."
              disabled={isAddingMergeSource}
            />
            <div className="max-h-40 overflow-auto rounded-md border border-border">
              {(mergeCandidates ?? []).length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted-foreground">
                  No tasks available to attach.
                </p>
              ) : (
                (mergeCandidates ?? []).map((candidate) => (
                  <button
                    key={candidate._id}
                    type="button"
                    onClick={() => onSelectedMergeTaskIdChange(candidate._id)}
                    className={`flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-muted/50 ${
                      selectedMergeTaskId === candidate._id ? "bg-muted" : ""
                    }`}
                    disabled={isAddingMergeSource}
                  >
                    <span>{candidate.title}</span>
                    {candidate.description && (
                      <span className="text-xs text-muted-foreground">{candidate.description}</span>
                    )}
                  </button>
                ))
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={() => void onAddMergeSource()}
                disabled={!selectedMergeTaskId || isAddingMergeSource}
              >
                {isAddingMergeSource ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Attaching...
                  </>
                ) : (
                  <>
                    <Plus className="h-3.5 w-3.5" />
                    Attach Task
                  </>
                )}
              </Button>
            </div>
            {addMergeSourceError && <p className="text-xs text-red-500">{addMergeSourceError}</p>}
          </div>
        </div>
      ) : (
        <div className="space-y-2 rounded-md border border-border p-3">
          <div>
            <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Merge With Another Task
            </h4>
            <p className="mt-1 text-xs text-muted-foreground">
              Create a new task from this task and another source task. The merged task will enter
              review.
            </p>
          </div>
          <Input
            value={mergeQuery}
            onChange={(event) => onMergeQueryChange(event.target.value)}
            placeholder="Search task to merge..."
            disabled={isMergeLockedSource}
          />
          <div className="max-h-40 overflow-auto rounded-md border border-border">
            {(mergeCandidates ?? []).length === 0 ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">No merge candidates found.</p>
            ) : (
              (mergeCandidates ?? []).map((candidate) => (
                <button
                  key={candidate._id}
                  type="button"
                  onClick={() => onSelectedMergeTaskIdChange(candidate._id)}
                  className={`flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-muted/50 ${
                    selectedMergeTaskId === candidate._id ? "bg-muted" : ""
                  }`}
                  disabled={isMergeLockedSource}
                >
                  <span>{candidate.title}</span>
                  {candidate.description && (
                    <span className="text-xs text-muted-foreground">{candidate.description}</span>
                  )}
                </button>
              ))
            )}
          </div>
          <Button
            size="sm"
            onClick={() => void onCreateMergeTask()}
            disabled={!selectedMergeTaskId || isCreatingMergeTask || isMergeLockedSource}
          >
            {isCreatingMergeTask ? "Creating..." : "Merge and Send To Review"}
          </Button>
          {createMergeTaskError && <p className="text-xs text-red-500">{createMergeTaskError}</p>}
        </div>
      )}
      <div>
        <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Trust Level
        </h4>
        <p className="mt-1 text-sm text-foreground">{task.trustLevel.replaceAll("_", " ")}</p>
      </div>
      {task.reviewers && task.reviewers.length > 0 && (
        <div>
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Reviewers
          </h4>
          <div className="mt-1 flex flex-wrap gap-1">
            {task.reviewers.map((reviewer) => (
              <Badge key={reviewer} variant="secondary" className="text-xs">
                {reviewer}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {task.taskTimeout != null && (
        <div>
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Task Timeout
          </h4>
          <p className="mt-1 text-sm text-foreground">{task.taskTimeout}s</p>
        </div>
      )}
      {task.interAgentTimeout != null && (
        <div>
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Inter-Agent Timeout
          </h4>
          <p className="mt-1 text-sm text-foreground">{task.interAgentTimeout}s</p>
        </div>
      )}
      <div>
        <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Tags</h4>
        <div className="mt-1 flex flex-wrap items-center gap-1">
          {(task.tags ?? []).map((tag) => {
            const colorKey = tagColorMap[tag];
            const color = colorKey ? TAG_COLORS[colorKey] : null;
            return (
              <span
                key={tag}
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
                  color ? `${color.bg} ${color.text}` : "bg-muted text-muted-foreground"
                }`}
              >
                {color && (
                  <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${color.dot}`} />
                )}
                {tag}
                {!isMergeLockedSource && (
                  <button
                    onClick={() => onRemoveTag(tag)}
                    className="ml-0.5 rounded-full p-0.5 transition-colors hover:bg-black/10"
                    aria-label={`Remove tag ${tag}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </span>
            );
          })}
          {!isMergeLockedSource && (
            <Popover>
              <PopoverTrigger asChild>
                <button
                  className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-dashed border-muted-foreground/40 text-muted-foreground transition-colors hover:border-foreground hover:text-foreground"
                  aria-label="Add tag"
                >
                  <Plus className="h-3 w-3" />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-48 p-2" align="start">
                {tagsList === undefined ? (
                  <p className="p-2 text-xs text-muted-foreground">Loading...</p>
                ) : tagsList.length === 0 ? (
                  <p className="p-2 text-xs text-muted-foreground">
                    No tags defined. Open the Tags panel to create some.
                  </p>
                ) : (
                  <div className="flex flex-col gap-0.5">
                    {tagsList.map((catalogTag) => {
                      const isAssigned = (task.tags ?? []).includes(catalogTag.name);
                      const color = TAG_COLORS[catalogTag.color];
                      return (
                        <button
                          key={catalogTag._id}
                          className={`flex items-center gap-2 rounded px-2 py-1.5 text-left text-xs transition-colors ${
                            isAssigned
                              ? "cursor-default opacity-50"
                              : "cursor-pointer hover:bg-muted"
                          }`}
                          onClick={() => !isAssigned && onAddTag(catalogTag.name)}
                          disabled={isAssigned}
                        >
                          {color && (
                            <span className={`h-2 w-2 flex-shrink-0 rounded-full ${color.dot}`} />
                          )}
                          <span className="flex-1">{catalogTag.name}</span>
                          {isAssigned && (
                            <span className="text-[10px] text-muted-foreground">Added</span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </PopoverContent>
            </Popover>
          )}
        </div>

        {tagAttributesList && tagAttributesList.length > 0 && (task.tags ?? []).length > 0 && (
          <div className="mt-3 space-y-1">
            {(task.tags ?? []).map((tag) => {
              const isExpanded = expandedTags.has(tag);
              const colorKey = tagColorMap[tag];
              const color = colorKey ? TAG_COLORS[colorKey] : null;

              return (
                <div key={`attrs-${tag}`} className="rounded-md border border-border">
                  <button
                    onClick={() => onToggleTagExpansion(tag)}
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors hover:bg-muted/50"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                    )}
                    {color && (
                      <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${color.dot}`} />
                    )}
                    <span className="font-medium">{tag}</span>
                    <span className="text-muted-foreground">attributes</span>
                  </button>
                  {isExpanded && (
                    <div className="space-y-1.5 px-3 pb-2">
                      {tagAttributesList.map((attr) => {
                        const val = tagAttrValues?.find(
                          (value) => value.tagName === tag && value.attributeId === attr._id,
                        );
                        return (
                          <TagAttributeEditor
                            key={`${tag}-${attr._id}`}
                            taskId={task._id}
                            tagName={tag}
                            attribute={attr}
                            currentValue={val?.value ?? ""}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useMemo, useState, type ChangeEventHandler, type RefObject } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { TabsContent } from "@/components/ui/tabs";
import {
  Archive,
  ArchiveRestore,
  ChevronRight,
  Eye,
  EyeOff,
  File,
  FileCode,
  FileText,
  Folder,
  Image,
  Loader2,
  Paperclip,
  Star,
  Trash2,
} from "lucide-react";
import type { Doc } from "@/convex/_generated/dataModel";
import type { DetailFileRef } from "@/features/tasks/hooks/useTaskDetailView";

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]);
const CODE_EXTS = new Set([".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".sh"]);

function truncate(text: string, max: number) {
  return text.length > max ? text.slice(0, max - 1) + "\u2026" : text;
}

function getDisplayFileKey(file: {
  name: string;
  subfolder: string;
  sourceTaskId?: DetailFileRef["sourceTaskId"];
}) {
  return `${file.sourceTaskId ?? "local"}:${file.subfolder}:${file.name}`;
}

function FileIcon({ name }: { name: string }) {
  const dotIdx = name.lastIndexOf(".");
  const ext = dotIdx > 0 ? name.slice(dotIdx).toLowerCase() : "";
  if (ext === ".pdf") {
    return (
      <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="PDF file" />
    );
  }
  if (IMAGE_EXTS.has(ext)) {
    return (
      <Image className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Image file" />
    );
  }
  if (CODE_EXTS.has(ext)) {
    return (
      <FileCode className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Code file" />
    );
  }
  return <File className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Generic file" />;
}

// --- Tree building ---

type FileTreeNode = {
  name: string;
  file?: DetailFileRef;
  children: Map<string, FileTreeNode>;
};

function buildFileTree(files: DetailFileRef[]): FileTreeNode {
  const root: FileTreeNode = { name: "", children: new Map() };
  for (const file of files) {
    const parts = file.name.split("/");
    let current = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const segment = parts[i];
      if (!current.children.has(segment)) {
        current.children.set(segment, { name: segment, children: new Map() });
      }
      current = current.children.get(segment)!;
    }
    const leafName = parts[parts.length - 1];
    current.children.set(file.name, { name: leafName, file, children: new Map() });
  }
  return root;
}

// --- Source task grouping ---

function groupBySource(files: DetailFileRef[]) {
  const local: DetailFileRef[] = [];
  const bySource = new Map<string, { title: string; label: string; files: DetailFileRef[] }>();

  for (const file of files) {
    if (!file.sourceTaskId) {
      local.push(file);
    } else {
      const key = file.sourceTaskId;
      if (!bySource.has(key)) {
        bySource.set(key, {
          title: file.sourceTaskTitle ?? "Unknown task",
          label: file.sourceLabel ?? "",
          files: [],
        });
      }
      bySource.get(key)!.files.push(file);
    }
  }
  return { local, bySource };
}

// --- File row ---

function FileRow({
  file,
  onOpenFile,
  indent = 0,
  onDeleteFile,
  deletingFiles,
  isMergeLockedSource,
  showDelete = false,
  hideSourceLabel = false,
  stepTitle,
  onToggleFavorite,
  onToggleArchive,
}: {
  file: DetailFileRef;
  onOpenFile: (file: DetailFileRef) => void;
  indent?: number;
  onDeleteFile?: (file: DetailFileRef) => void | Promise<void>;
  deletingFiles?: Set<string>;
  isMergeLockedSource?: boolean;
  showDelete?: boolean;
  hideSourceLabel?: boolean;
  stepTitle?: string;
  onToggleFavorite?: (file: DetailFileRef) => void;
  onToggleArchive?: (file: DetailFileRef) => void;
}) {
  const key = getDisplayFileKey(file);
  const isDeleting = deletingFiles?.has(key) ?? false;
  const canDelete = showDelete && !file.sourceTaskId && !isMergeLockedSource;
  const isFavorite = file.isFavorite === true;
  const isArchived = file.isArchived === true;

  return (
    <div
      className={`group flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition-opacity hover:bg-muted/50 animate-in fade-in duration-300 ${
        isDeleting ? "pointer-events-none opacity-40" : ""
      } ${isArchived ? "opacity-50" : ""}`}
      style={{ paddingLeft: `${8 + indent * 16}px` }}
      onClick={() => onOpenFile(file)}
      data-testid="file-row"
    >
      {onToggleFavorite && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleFavorite(file);
          }}
          className="flex-shrink-0"
          aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
        >
          <Star
            className={`h-3.5 w-3.5 transition-colors ${
              isFavorite
                ? "fill-amber-400 text-amber-400"
                : "text-muted-foreground/40 hover:text-amber-400"
            }`}
          />
        </button>
      )}
      <FileIcon name={file.name} />
      <span className="min-w-0 flex-1 truncate text-sm">{file.name.split("/").pop()}</span>
      {stepTitle && (
        <Badge variant="outline" className="flex-shrink-0 text-[10px] font-normal">
          {truncate(stepTitle, 25)}
        </Badge>
      )}
      {!hideSourceLabel && file.sourceLabel && (
        <Badge variant="secondary" className="text-[10px]">
          {file.sourceLabel}
        </Badge>
      )}
      <span className="flex-shrink-0 text-xs text-muted-foreground">{formatSize(file.size)}</span>
      {onToggleArchive && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleArchive(file);
          }}
          className={`flex-shrink-0 text-muted-foreground transition-opacity hover:text-foreground ${
            isArchived ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          }`}
          aria-label={isArchived ? "Restore from archive" : "Archive file"}
        >
          {isArchived ? (
            <ArchiveRestore className="h-3.5 w-3.5" />
          ) : (
            <Archive className="h-3.5 w-3.5" />
          )}
        </button>
      )}
      {canDelete && onDeleteFile && (
        <button
          onClick={(event) => {
            event.stopPropagation();
            void onDeleteFile(file);
          }}
          disabled={isDeleting}
          className={`flex-shrink-0 text-muted-foreground transition-opacity hover:text-destructive ${
            isDeleting ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          }`}
          aria-label="Delete attachment"
        >
          {isDeleting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Trash2 className="h-3.5 w-3.5" />
          )}
        </button>
      )}
    </div>
  );
}

// --- Folder group ---

function FolderGroup({
  node,
  onOpenFile,
  indent = 0,
  onDeleteFile,
  deletingFiles,
  isMergeLockedSource,
  showDelete = false,
  hideSourceLabel = false,
  stepTitle,
  onToggleFavorite,
  onToggleArchive,
}: {
  node: FileTreeNode;
  onOpenFile: (file: DetailFileRef) => void;
  indent?: number;
  onDeleteFile?: (file: DetailFileRef) => void | Promise<void>;
  deletingFiles?: Set<string>;
  isMergeLockedSource?: boolean;
  showDelete?: boolean;
  hideSourceLabel?: boolean;
  stepTitle?: string;
  onToggleFavorite?: (file: DetailFileRef) => void;
  onToggleArchive?: (file: DetailFileRef) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const entries = Array.from(node.children.values());
  const folders = entries.filter((e) => !e.file).sort((a, b) => a.name.localeCompare(b.name));
  const files = entries.filter((e) => e.file).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div>
      {node.name && (
        <button
          className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-muted/50"
          style={{ paddingLeft: `${8 + indent * 16}px` }}
          onClick={() => setExpanded(!expanded)}
        >
          <ChevronRight
            className={`h-3.5 w-3.5 flex-shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
          />
          <Folder className="h-4 w-4 flex-shrink-0" />
          <span className="truncate font-medium">{node.name}</span>
        </button>
      )}
      {expanded && (
        <div>
          {folders.map((folder) => (
            <FolderGroup
              key={folder.name}
              node={folder}
              onOpenFile={onOpenFile}
              indent={node.name ? indent + 1 : indent}
              onDeleteFile={onDeleteFile}
              deletingFiles={deletingFiles}
              isMergeLockedSource={isMergeLockedSource}
              showDelete={showDelete}
              hideSourceLabel={hideSourceLabel}
              stepTitle={stepTitle}
              onToggleFavorite={onToggleFavorite}
              onToggleArchive={onToggleArchive}
            />
          ))}
          {files.map((leaf) => (
            <FileRow
              key={leaf.file!.name}
              file={leaf.file!}
              onOpenFile={onOpenFile}
              indent={node.name ? indent + 1 : indent}
              onDeleteFile={onDeleteFile}
              deletingFiles={deletingFiles}
              isMergeLockedSource={isMergeLockedSource}
              showDelete={showDelete}
              hideSourceLabel={hideSourceLabel}
              stepTitle={stepTitle}
              onToggleFavorite={onToggleFavorite}
              onToggleArchive={onToggleArchive}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// --- Render a file tree from a list of files ---

function FileTreeSection({
  files,
  onOpenFile,
  onDeleteFile,
  deletingFiles,
  isMergeLockedSource,
  showDelete = false,
  hideSourceLabel = false,
  stepTitle,
  onToggleFavorite,
  onToggleArchive,
}: {
  files: DetailFileRef[];
  onOpenFile: (file: DetailFileRef) => void;
  onDeleteFile?: (file: DetailFileRef) => void | Promise<void>;
  deletingFiles?: Set<string>;
  isMergeLockedSource?: boolean;
  showDelete?: boolean;
  hideSourceLabel?: boolean;
  stepTitle?: string;
  onToggleFavorite?: (file: DetailFileRef) => void;
  onToggleArchive?: (file: DetailFileRef) => void;
}) {
  const tree = buildFileTree(files);
  return (
    <FolderGroup
      node={tree}
      onOpenFile={onOpenFile}
      onDeleteFile={onDeleteFile}
      deletingFiles={deletingFiles}
      isMergeLockedSource={isMergeLockedSource}
      showDelete={showDelete}
      hideSourceLabel={hideSourceLabel}
      stepTitle={stepTitle}
      onToggleFavorite={onToggleFavorite}
      onToggleArchive={onToggleArchive}
    />
  );
}

// --- Source task group ---

function SourceTaskGroup({
  title,
  label,
  files,
  onOpenFile,
  onDeleteFile,
  deletingFiles,
  isMergeLockedSource,
  showDelete = false,
  onToggleFavorite,
  onToggleArchive,
}: {
  title: string;
  label: string;
  files: DetailFileRef[];
  onOpenFile: (file: DetailFileRef) => void;
  onDeleteFile?: (file: DetailFileRef) => void | Promise<void>;
  deletingFiles?: Set<string>;
  isMergeLockedSource?: boolean;
  showDelete?: boolean;
  onToggleFavorite?: (file: DetailFileRef) => void;
  onToggleArchive?: (file: DetailFileRef) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  return (
    <div className="mt-1 rounded-md border border-dashed border-muted-foreground/25">
      <button
        className="flex w-full items-center gap-1.5 px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted/30"
        onClick={() => setExpanded(!expanded)}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 flex-shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
        <span className="min-w-0 flex-1 truncate text-left">
          <span className="text-xs text-muted-foreground/70">From: </span>
          <span className="font-medium">&ldquo;{title}&rdquo;</span>
          {label && <span className="ml-1 text-xs text-muted-foreground/70">({label})</span>}
        </span>
        <span className="flex-shrink-0 text-xs text-muted-foreground/70">
          {files.length} {files.length === 1 ? "file" : "files"}, {formatSize(totalSize)}
        </span>
      </button>
      {expanded && (
        <div className="pb-1">
          <FileTreeSection
            files={files}
            onOpenFile={onOpenFile}
            onDeleteFile={onDeleteFile}
            deletingFiles={deletingFiles}
            isMergeLockedSource={isMergeLockedSource}
            showDelete={showDelete}
            hideSourceLabel
            onToggleFavorite={onToggleFavorite}
            onToggleArchive={onToggleArchive}
          />
        </div>
      )}
    </div>
  );
}

// --- Step group ---

function StepGroup({
  stepTitle,
  files,
  onOpenFile,
  onDeleteFile,
  deletingFiles,
  isMergeLockedSource,
  onToggleFavorite,
  onToggleArchive,
  defaultExpanded = false,
}: {
  stepTitle: string;
  files: DetailFileRef[];
  onOpenFile: (file: DetailFileRef) => void;
  onDeleteFile?: (file: DetailFileRef) => void | Promise<void>;
  deletingFiles?: Set<string>;
  isMergeLockedSource?: boolean;
  onToggleFavorite?: (file: DetailFileRef) => void;
  onToggleArchive?: (file: DetailFileRef) => void;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const { local, bySource } = groupBySource(files);

  return (
    <div>
      <button
        className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted/50"
        onClick={() => setExpanded(!expanded)}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 flex-shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
        <span className="min-w-0 flex-1 truncate text-left font-medium">
          {truncate(stepTitle, 40)}
        </span>
        <Badge variant="secondary" className="text-[10px]">
          {files.length}
        </Badge>
      </button>
      {expanded && (
        <div className="ml-2 border-l border-muted-foreground/15 pl-1">
          {local.length > 0 && (
            <FileTreeSection
              files={local}
              onOpenFile={onOpenFile}
              onDeleteFile={onDeleteFile}
              deletingFiles={deletingFiles}
              isMergeLockedSource={isMergeLockedSource}
              onToggleFavorite={onToggleFavorite}
              onToggleArchive={onToggleArchive}
            />
          )}
          {Array.from(bySource.entries()).map(([sourceId, source]) => (
            <SourceTaskGroup
              key={sourceId}
              title={source.title}
              label={source.label}
              files={source.files}
              onOpenFile={onOpenFile}
              onDeleteFile={onDeleteFile}
              deletingFiles={deletingFiles}
              isMergeLockedSource={isMergeLockedSource}
              onToggleFavorite={onToggleFavorite}
              onToggleArchive={onToggleArchive}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// --- Main component ---

type StepInfo = Pick<Doc<"steps">, "_id" | "title" | "order">;

interface TaskDetailFilesTabProps {
  displayFiles: DetailFileRef[];
  steps: StepInfo[];
  attachInputRef: RefObject<HTMLInputElement | null>;
  onAttachFiles: ChangeEventHandler<HTMLInputElement>;
  isMergeLockedSource: boolean;
  isUploading: boolean;
  uploadError: string;
  deleteError: string;
  deletingFiles: Set<string>;
  onOpenFile: (file: DetailFileRef) => void;
  onDeleteFile: (file: DetailFileRef) => void | Promise<void>;
  onToggleFavorite: (file: DetailFileRef) => void;
  onToggleArchive: (file: DetailFileRef) => void;
}

export function TaskDetailFilesTab({
  displayFiles,
  steps,
  attachInputRef,
  onAttachFiles,
  isMergeLockedSource,
  isUploading,
  uploadError,
  deleteError,
  deletingFiles,
  onOpenFile,
  onDeleteFile,
  onToggleFavorite,
  onToggleArchive,
}: TaskDetailFilesTabProps) {
  const [showArchived, setShowArchived] = useState(false);

  const stepMap = useMemo(() => {
    const map = new Map<string, StepInfo>();
    for (const step of steps) {
      map.set(step._id, step);
    }
    return map;
  }, [steps]);

  const archivedCount = useMemo(
    () => displayFiles.filter((f) => f.isArchived).length,
    [displayFiles],
  );

  const visibleFiles = useMemo(
    () => (showArchived ? displayFiles : displayFiles.filter((f) => !f.isArchived)),
    [displayFiles, showArchived],
  );

  const {
    favorites,
    stepGroups,
    localAttachments,
    attachmentSources,
    localUngrouped,
    ungroupedSources,
  } = useMemo(() => {
    const favs: DetailFileRef[] = [];
    const byStep = new Map<string, DetailFileRef[]>();
    const attachs: DetailFileRef[] = [];
    const ungrouped: DetailFileRef[] = [];

    for (const file of visibleFiles) {
      if (file.isFavorite) {
        favs.push(file);
        continue;
      }

      if (file.subfolder === "attachments") {
        attachs.push(file);
      } else if (file.stepId) {
        const stepId = file.stepId as string;
        if (!byStep.has(stepId)) byStep.set(stepId, []);
        byStep.get(stepId)!.push(file);
      } else {
        ungrouped.push(file);
      }
    }

    const sortedStepGroups = Array.from(byStep.entries())
      .map(([stepId, files]) => ({
        stepId,
        stepTitle: stepMap.get(stepId)?.title ?? "Unknown step",
        order: stepMap.get(stepId)?.order ?? Infinity,
        files,
      }))
      .sort((a, b) => a.order - b.order);

    const { local: localAtt, bySource: attSources } = groupBySource(attachs);
    const { local: localUng, bySource: ungSources } = groupBySource(ungrouped);

    return {
      favorites: favs,
      stepGroups: sortedStepGroups,
      localAttachments: localAtt,
      attachmentSources: attSources,
      localUngrouped: localUng,
      ungroupedSources: ungSources,
    };
  }, [visibleFiles, stepMap]);

  const hasAttachments = localAttachments.length > 0 || attachmentSources.size > 0;
  const hasUngrouped = localUngrouped.length > 0 || ungroupedSources.size > 0;

  const hasContent = visibleFiles.length > 0;

  return (
    <TabsContent value="files" className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col">
      <ScrollArea className="flex-1 px-6 py-4">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <input
              type="file"
              multiple
              ref={attachInputRef}
              onChange={onAttachFiles}
              className="hidden"
            />
            {!isMergeLockedSource && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => attachInputRef.current?.click()}
                disabled={isUploading}
                data-testid="attach-file-button"
              >
                <Paperclip className="mr-1.5 h-3.5 w-3.5" />
                {isUploading ? "Uploading..." : "Attach File"}
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {uploadError && (
              <p className="text-xs text-red-500" data-testid="upload-error">
                {uploadError}
              </p>
            )}
            {archivedCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1 text-xs text-muted-foreground"
                onClick={() => setShowArchived(!showArchived)}
              >
                {showArchived ? (
                  <EyeOff className="h-3.5 w-3.5" />
                ) : (
                  <Eye className="h-3.5 w-3.5" />
                )}
                {archivedCount} archived
              </Button>
            )}
          </div>
        </div>
        {deleteError && (
          <p className="mb-3 text-xs text-red-500" data-testid="delete-error">
            {deleteError}
          </p>
        )}

        {!hasContent && displayFiles.length === 0 ? (
          <p
            className="py-8 text-center text-sm text-muted-foreground"
            data-testid="files-empty-placeholder"
          >
            No files yet. Attach files or wait for agent output.
          </p>
        ) : !hasContent ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            All files are archived. Click &ldquo;Show archived&rdquo; to see them.
          </p>
        ) : (
          <div className="space-y-4">
            {/* Favorites section */}
            {favorites.length > 0 && (
              <div>
                <div className="mb-1.5 flex items-center gap-1.5">
                  <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Favorites
                  </span>
                </div>
                <div className="flex flex-col gap-0.5">
                  {favorites.map((file) => (
                    <FileRow
                      key={getDisplayFileKey(file)}
                      file={file}
                      onOpenFile={onOpenFile}
                      onDeleteFile={onDeleteFile}
                      deletingFiles={deletingFiles}
                      isMergeLockedSource={isMergeLockedSource}
                      showDelete={file.subfolder === "attachments"}
                      stepTitle={
                        file.stepId ? stepMap.get(file.stepId as string)?.title : undefined
                      }
                      onToggleFavorite={onToggleFavorite}
                      onToggleArchive={onToggleArchive}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Step groups */}
            {stepGroups.map((group, index) => (
              <StepGroup
                key={group.stepId}
                stepTitle={group.stepTitle}
                files={group.files}
                onOpenFile={onOpenFile}
                onDeleteFile={onDeleteFile}
                deletingFiles={deletingFiles}
                isMergeLockedSource={isMergeLockedSource}
                onToggleFavorite={onToggleFavorite}
                onToggleArchive={onToggleArchive}
                defaultExpanded={index === stepGroups.length - 1}
              />
            ))}

            {/* Attachments section */}
            {hasAttachments && (
              <div>
                <div className="mb-1.5 flex items-center gap-1.5">
                  <Paperclip className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Attachments
                  </span>
                </div>
                <div className="flex flex-col gap-0.5">
                  {localAttachments.length > 0 && (
                    <FileTreeSection
                      files={localAttachments}
                      onOpenFile={onOpenFile}
                      onDeleteFile={onDeleteFile}
                      deletingFiles={deletingFiles}
                      isMergeLockedSource={isMergeLockedSource}
                      showDelete
                      onToggleFavorite={onToggleFavorite}
                      onToggleArchive={onToggleArchive}
                    />
                  )}
                  {Array.from(attachmentSources.entries()).map(([sourceId, source]) => (
                    <SourceTaskGroup
                      key={sourceId}
                      title={source.title}
                      label={source.label}
                      files={source.files}
                      onOpenFile={onOpenFile}
                      onToggleFavorite={onToggleFavorite}
                      onToggleArchive={onToggleArchive}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Ungrouped outputs */}
            {hasUngrouped && (
              <div>
                <h4 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Other outputs
                </h4>
                <div className="flex flex-col gap-0.5">
                  {localUngrouped.length > 0 && (
                    <FileTreeSection
                      files={localUngrouped}
                      onOpenFile={onOpenFile}
                      onToggleFavorite={onToggleFavorite}
                      onToggleArchive={onToggleArchive}
                    />
                  )}
                  {Array.from(ungroupedSources.entries()).map(([sourceId, source]) => (
                    <SourceTaskGroup
                      key={sourceId}
                      title={source.title}
                      label={source.label}
                      files={source.files}
                      onOpenFile={onOpenFile}
                      onToggleFavorite={onToggleFavorite}
                      onToggleArchive={onToggleArchive}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </ScrollArea>
    </TabsContent>
  );
}

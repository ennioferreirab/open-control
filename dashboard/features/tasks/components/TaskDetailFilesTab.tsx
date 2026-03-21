"use client";

import { useState, type ChangeEventHandler, type RefObject } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { TabsContent } from "@/components/ui/tabs";
import {
  ChevronRight,
  File,
  FileCode,
  FileText,
  Folder,
  Image,
  Loader2,
  Paperclip,
  Trash2,
} from "lucide-react";
import type { DetailFileRef } from "@/features/tasks/hooks/useTaskDetailView";

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]);
const CODE_EXTS = new Set([".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".sh"]);

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
}: {
  file: DetailFileRef;
  onOpenFile: (file: DetailFileRef) => void;
  indent?: number;
  onDeleteFile?: (file: DetailFileRef) => void | Promise<void>;
  deletingFiles?: Set<string>;
  isMergeLockedSource?: boolean;
  showDelete?: boolean;
  hideSourceLabel?: boolean;
}) {
  const key = getDisplayFileKey(file);
  const isDeleting = deletingFiles?.has(key) ?? false;
  const canDelete = showDelete && !file.sourceTaskId && !isMergeLockedSource;

  return (
    <div
      className={`group flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition-opacity hover:bg-muted/50 animate-in fade-in duration-300 ${
        isDeleting ? "pointer-events-none opacity-40" : ""
      }`}
      style={{ paddingLeft: `${8 + indent * 16}px` }}
      onClick={() => onOpenFile(file)}
      data-testid="file-row"
    >
      <FileIcon name={file.name} />
      <span className="min-w-0 flex-1 truncate text-sm">{file.name.split("/").pop()}</span>
      {!hideSourceLabel && file.sourceLabel && (
        <Badge variant="secondary" className="text-[10px]">
          {file.sourceLabel}
        </Badge>
      )}
      <span className="flex-shrink-0 text-xs text-muted-foreground">{formatSize(file.size)}</span>
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
}: {
  node: FileTreeNode;
  onOpenFile: (file: DetailFileRef) => void;
  indent?: number;
  onDeleteFile?: (file: DetailFileRef) => void | Promise<void>;
  deletingFiles?: Set<string>;
  isMergeLockedSource?: boolean;
  showDelete?: boolean;
  hideSourceLabel?: boolean;
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
}: {
  files: DetailFileRef[];
  onOpenFile: (file: DetailFileRef) => void;
  onDeleteFile?: (file: DetailFileRef) => void | Promise<void>;
  deletingFiles?: Set<string>;
  isMergeLockedSource?: boolean;
  showDelete?: boolean;
  hideSourceLabel?: boolean;
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
}: {
  title: string;
  label: string;
  files: DetailFileRef[];
  onOpenFile: (file: DetailFileRef) => void;
  onDeleteFile?: (file: DetailFileRef) => void | Promise<void>;
  deletingFiles?: Set<string>;
  isMergeLockedSource?: boolean;
  showDelete?: boolean;
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
          />
        </div>
      )}
    </div>
  );
}

// --- Main component ---

interface TaskDetailFilesTabProps {
  displayFiles: DetailFileRef[];
  attachInputRef: RefObject<HTMLInputElement | null>;
  onAttachFiles: ChangeEventHandler<HTMLInputElement>;
  isMergeLockedSource: boolean;
  isUploading: boolean;
  uploadError: string;
  deleteError: string;
  deletingFiles: Set<string>;
  onOpenFile: (file: DetailFileRef) => void;
  onDeleteFile: (file: DetailFileRef) => void | Promise<void>;
}

export function TaskDetailFilesTab({
  displayFiles,
  attachInputRef,
  onAttachFiles,
  isMergeLockedSource,
  isUploading,
  uploadError,
  deleteError,
  deletingFiles,
  onOpenFile,
  onDeleteFile,
}: TaskDetailFilesTabProps) {
  const attachments = displayFiles.filter((file) => file.subfolder === "attachments");
  const outputs = displayFiles.filter((file) => file.subfolder === "output");

  const { local: localAttachments, bySource: attachmentSources } = groupBySource(attachments);
  const { local: localOutputs, bySource: outputSources } = groupBySource(outputs);

  return (
    <TabsContent value="files" className="flex-1 min-h-0 m-0 data-[state=active]:flex flex-col">
      <ScrollArea className="flex-1 px-6 py-4">
        <div className="mb-4 flex items-center justify-between">
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
          {uploadError && (
            <p className="text-xs text-red-500" data-testid="upload-error">
              {uploadError}
            </p>
          )}
        </div>
        {deleteError && (
          <p className="mb-3 text-xs text-red-500" data-testid="delete-error">
            {deleteError}
          </p>
        )}

        {displayFiles.length === 0 ? (
          <p
            className="py-8 text-center text-sm text-muted-foreground"
            data-testid="files-empty-placeholder"
          >
            No files yet. Attach files or wait for agent output.
          </p>
        ) : (
          <div className="space-y-6">
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Attachments
              </h4>
              {attachments.length === 0 ? (
                <p className="py-2 text-sm text-muted-foreground">No attachments yet.</p>
              ) : (
                <div className="flex flex-col gap-1">
                  {localAttachments.length > 0 && (
                    <FileTreeSection
                      files={localAttachments}
                      onOpenFile={onOpenFile}
                      onDeleteFile={onDeleteFile}
                      deletingFiles={deletingFiles}
                      isMergeLockedSource={isMergeLockedSource}
                      showDelete
                    />
                  )}
                  {Array.from(attachmentSources.entries()).map(([sourceId, source]) => (
                    <SourceTaskGroup
                      key={sourceId}
                      title={source.title}
                      label={source.label}
                      files={source.files}
                      onOpenFile={onOpenFile}
                    />
                  ))}
                </div>
              )}
            </div>

            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Outputs
              </h4>
              {outputs.length === 0 ? (
                <p className="py-2 text-sm text-muted-foreground">No outputs yet.</p>
              ) : (
                <div className="flex flex-col gap-1">
                  {localOutputs.length > 0 && (
                    <FileTreeSection files={localOutputs} onOpenFile={onOpenFile} />
                  )}
                  {Array.from(outputSources.entries()).map(([sourceId, source]) => (
                    <SourceTaskGroup
                      key={sourceId}
                      title={source.title}
                      label={source.label}
                      files={source.files}
                      onOpenFile={onOpenFile}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </ScrollArea>
    </TabsContent>
  );
}

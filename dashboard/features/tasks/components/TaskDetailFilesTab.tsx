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

/** Get display name (last segment of the path). */
function displayName(name: string) {
  const idx = name.lastIndexOf("/");
  return idx >= 0 ? name.slice(idx + 1) : name;
}

/**
 * Group files into a folder tree (up to 2 levels deep).
 * Returns { rootFiles, folders } where folders is a map of
 * folderName -> { files, subfolders: Map<subName, files[]> }.
 */
function buildOutputTree(files: DetailFileRef[]) {
  const rootFiles: DetailFileRef[] = [];
  const folders = new Map<
    string,
    { files: DetailFileRef[]; subfolders: Map<string, DetailFileRef[]> }
  >();

  for (const file of files) {
    const parts = file.name.split("/");
    if (parts.length === 1) {
      rootFiles.push(file);
    } else if (parts.length === 2) {
      const folder = parts[0]!;
      if (!folders.has(folder)) {
        folders.set(folder, { files: [], subfolders: new Map() });
      }
      folders.get(folder)!.files.push(file);
    } else {
      // 3+ segments — group under first two levels
      const folder = parts[0]!;
      const subfolder = parts[1]!;
      if (!folders.has(folder)) {
        folders.set(folder, { files: [], subfolders: new Map() });
      }
      const entry = folders.get(folder)!;
      if (!entry.subfolders.has(subfolder)) {
        entry.subfolders.set(subfolder, []);
      }
      entry.subfolders.get(subfolder)!.push(file);
    }
  }

  return { rootFiles, folders };
}

function FolderTotalSize({ files }: { files: DetailFileRef[] }) {
  const total = files.reduce((sum, f) => sum + f.size, 0);
  return (
    <span className="flex-shrink-0 text-xs text-muted-foreground">{formatSize(total)}</span>
  );
}

function OutputFileRow({
  file,
  onOpenFile,
  indent = 0,
}: {
  file: DetailFileRef;
  onOpenFile: (file: DetailFileRef) => void;
  indent?: number;
}) {
  return (
    <div
      key={getDisplayFileKey(file)}
      className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 animate-in fade-in duration-300"
      style={indent > 0 ? { paddingLeft: `${indent * 16 + 8}px` } : undefined}
      onClick={() => onOpenFile(file)}
    >
      <FileIcon name={file.name} />
      <span className="min-w-0 flex-1 truncate text-sm">{displayName(file.name)}</span>
      {file.sourceLabel && (
        <Badge variant="secondary" className="text-[10px]">
          {file.sourceLabel}
        </Badge>
      )}
      <span className="flex-shrink-0 text-xs text-muted-foreground">
        {formatSize(file.size)}
      </span>
    </div>
  );
}

function OutputFolderGroup({
  name,
  files,
  subfolders,
  onOpenFile,
  depth,
}: {
  name: string;
  files: DetailFileRef[];
  subfolders: Map<string, DetailFileRef[]>;
  onOpenFile: (file: DetailFileRef) => void;
  depth: number;
}) {
  const [open, setOpen] = useState(true);
  const allFiles = [...files, ...[...subfolders.values()].flat()];

  return (
    <div>
      <button
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted/50"
        style={depth > 0 ? { paddingLeft: `${depth * 16 + 8}px` } : undefined}
        onClick={() => setOpen(!open)}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 flex-shrink-0 text-muted-foreground transition-transform ${open ? "rotate-90" : ""}`}
        />
        <Folder className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate text-left font-medium">{name}</span>
        <span className="flex-shrink-0 text-xs text-muted-foreground">
          {allFiles.length} {allFiles.length === 1 ? "file" : "files"}
        </span>
        <FolderTotalSize files={allFiles} />
      </button>
      {open && (
        <div className="flex flex-col gap-0.5">
          {files.map((file) => (
            <OutputFileRow
              key={getDisplayFileKey(file)}
              file={file}
              onOpenFile={onOpenFile}
              indent={depth + 1}
            />
          ))}
          {[...subfolders.entries()].map(([subName, subFiles]) => (
            <OutputFolderGroup
              key={subName}
              name={subName}
              files={subFiles}
              subfolders={new Map()}
              onOpenFile={onOpenFile}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

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
  const { rootFiles, folders } = buildOutputTree(outputs);

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
                  {attachments.map((file) => {
                    const key = getDisplayFileKey(file);
                    const isDeleting = deletingFiles.has(key);
                    return (
                      <div
                        key={key}
                        className={`group flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition-opacity hover:bg-muted/50 animate-in fade-in duration-300 ${
                          isDeleting ? "pointer-events-none opacity-40" : ""
                        }`}
                        onClick={() => onOpenFile(file)}
                      >
                        <FileIcon name={file.name} />
                        <span className="min-w-0 flex-1 truncate text-sm">{file.name}</span>
                        {file.sourceLabel && (
                          <Badge variant="secondary" className="text-[10px]">
                            {file.sourceLabel}
                          </Badge>
                        )}
                        <span className="flex-shrink-0 text-xs text-muted-foreground">
                          {formatSize(file.size)}
                        </span>
                        {!file.sourceTaskId && !isMergeLockedSource && (
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
                  })}
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
                <div className="flex flex-col gap-0.5">
                  {rootFiles.map((file) => (
                    <OutputFileRow
                      key={getDisplayFileKey(file)}
                      file={file}
                      onOpenFile={onOpenFile}
                    />
                  ))}
                  {[...folders.entries()].map(([folderName, { files, subfolders }]) => (
                    <OutputFolderGroup
                      key={folderName}
                      name={folderName}
                      files={files}
                      subfolders={subfolders}
                      onOpenFile={onOpenFile}
                      depth={0}
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

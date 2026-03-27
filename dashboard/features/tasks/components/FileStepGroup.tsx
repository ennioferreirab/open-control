"use client";

import { useState } from "react";
import { ChevronRight, File, FileText, Image, Star } from "lucide-react";
import { cn } from "@/lib/utils";

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]);
const TEXT_EXTS = new Set([".md", ".txt", ".pdf"]);

function getFileIcon(name: string) {
  const dotIdx = name.lastIndexOf(".");
  const ext = dotIdx > 0 ? name.slice(dotIdx).toLowerCase() : "";
  if (TEXT_EXTS.has(ext)) return FileText;
  if (IMAGE_EXTS.has(ext)) return Image;
  return File;
}

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

export interface FileStepGroupFile {
  name: string;
  subfolder: string;
  type?: string;
  size?: number;
  isFavorite?: boolean;
  sourceTaskId?: string;
}

interface FileStepGroupProps {
  stepName: string;
  stepStatus?: string;
  files: FileStepGroupFile[];
  defaultExpanded?: boolean;
  onFileClick?: (file: FileStepGroupFile) => void;
  onToggleFavorite?: (file: FileStepGroupFile) => void;
}

const STEP_DOT_COLORS: Record<string, string> = {
  planned: "bg-slate-500",
  assigned: "bg-cyan-500",
  running: "bg-blue-500",
  review: "bg-amber-500",
  completed: "bg-green-500",
  crashed: "bg-red-500",
  blocked: "bg-amber-500",
  waiting_human: "bg-amber-500",
  deleted: "bg-gray-500",
};

function getStatusDotColor(status?: string): string {
  if (!status) return "bg-muted-foreground/40";
  return STEP_DOT_COLORS[status] ?? "bg-muted-foreground/40";
}

export function FileStepGroup({
  stepName,
  stepStatus,
  files,
  defaultExpanded = false,
  onFileClick,
  onToggleFavorite,
}: FileStepGroupProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-1.5 px-2 py-1 text-xs text-muted-foreground hover:bg-muted/50 rounded-md"
        data-testid="file-step-group-header"
      >
        <ChevronRight
          className={cn(
            "h-3 w-3 flex-shrink-0 transition-transform duration-150",
            expanded && "rotate-90",
          )}
        />
        <span
          className={cn(
            "h-[5px] w-[5px] flex-shrink-0 rounded-full",
            getStatusDotColor(stepStatus),
          )}
        />
        <span className="flex-1 truncate text-left">{stepName}</span>
        <span className="flex-shrink-0 text-[10px] text-muted-foreground/60">{files.length}</span>
      </button>
      {expanded && (
        <div className="ml-4 mt-0.5 flex flex-col gap-0.5">
          {files.map((file) => {
            const Icon = getFileIcon(file.name);
            return (
              <button
                key={`${file.subfolder}:${file.name}`}
                type="button"
                onClick={() => onFileClick?.(file)}
                className="group flex items-center gap-1.5 rounded-md px-2 py-1 hover:bg-muted/50"
                data-testid="file-step-group-file"
              >
                <Icon className="h-2.5 w-2.5 flex-shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate text-left text-xs text-muted-foreground">
                  {file.name.split("/").pop()}
                </span>
                {file.isFavorite && (
                  <Star className="h-2.5 w-2.5 flex-shrink-0 fill-amber-400 text-amber-400" />
                )}
                {onToggleFavorite && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleFavorite(file);
                    }}
                    className={cn(
                      "flex-shrink-0",
                      file.isFavorite ? "" : "opacity-0 group-hover:opacity-100",
                    )}
                    aria-label={file.isFavorite ? "Remove from favorites" : "Add to favorites"}
                  >
                    {!file.isFavorite && (
                      <Star className="h-2.5 w-2.5 text-muted-foreground/40 hover:text-amber-400" />
                    )}
                  </button>
                )}
                {file.size !== undefined && (
                  <span className="flex-shrink-0 text-[10px] text-muted-foreground/60">
                    {formatSize(file.size)}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

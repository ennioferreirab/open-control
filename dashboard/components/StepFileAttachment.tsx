"use client";

import { useRef, useState } from "react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import { Button } from "@/components/ui/button";
import {
  File,
  FileCode,
  FileText,
  Image,
  Loader2,
  Paperclip,
  X,
} from "lucide-react";

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]);
const CODE_EXTS = new Set([
  ".py",
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".go",
  ".rs",
  ".java",
  ".sh",
]);

function getFileIconType(name: string): "pdf" | "image" | "code" | "generic" {
  const dotIdx = name.lastIndexOf(".");
  if (dotIdx === -1) return "generic";
  const ext = name.slice(dotIdx).toLowerCase();
  if (ext === ".pdf") return "pdf";
  if (IMAGE_EXTS.has(ext)) return "image";
  if (CODE_EXTS.has(ext)) return "code";
  return "generic";
}

function FileIcon({ name }: { name: string }) {
  const iconType = getFileIconType(name);
  const cls = "h-3 w-3 text-muted-foreground";
  switch (iconType) {
    case "pdf":
      return <FileText className={cls} data-testid="icon-pdf" />;
    case "image":
      return <Image className={cls} data-testid="icon-image" />;
    case "code":
      return <FileCode className={cls} data-testid="icon-code" />;
    default:
      return <File className={cls} data-testid="icon-generic" />;
  }
}

export interface StepFileAttachmentProps {
  stepTempId: string;
  attachedFiles: string[];
  taskId: string;
  onFilesAttached: (stepTempId: string, fileNames: string[]) => void;
  onFileRemoved: (stepTempId: string, fileName: string) => void;
}

export function StepFileAttachment({
  stepTempId,
  attachedFiles,
  taskId,
  onFilesAttached,
  onFileRemoved,
}: StepFileAttachmentProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const addTaskFiles = useMutation(api.tasks.addTaskFiles);

  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    e.target.value = "";

    setIsUploading(true);
    setUploadError("");

    try {
      const formData = new FormData();
      for (const file of files) {
        formData.append("files", file, file.name);
      }
      const res = await fetch(`/api/tasks/${taskId}/files`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const { files: uploadedFiles } = await res.json();

      // Update the task-level files manifest
      await addTaskFiles({
        taskId: taskId as Id<"tasks">,
        files: uploadedFiles,
      });

      // Update the step's attachedFiles in the local plan state
      const newFileNames: string[] = uploadedFiles.map(
        (f: { name: string }) => f.name
      );
      // Deduplicate: only add file names not already in attachedFiles
      const existingNames = new Set(attachedFiles);
      const uniqueNewNames = newFileNames.filter(
        (name) => !existingNames.has(name)
      );
      if (uniqueNewNames.length > 0) {
        onFilesAttached(stepTempId, uniqueNewNames);
      }
    } catch {
      setUploadError("Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemoveFile = (fileName: string) => {
    onFileRemoved(stepTempId, fileName);
  };

  return (
    <div className="mt-2 space-y-1">
      {/* File list — only shown when there are attached files */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-col gap-0.5">
          {attachedFiles.map((fileName) => (
            <div
              key={fileName}
              className="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <FileIcon name={fileName} />
              <span className="flex-1 min-w-0 truncate" title={fileName}>
                {fileName}
              </span>
              <button
                onClick={() => handleRemoveFile(fileName)}
                aria-label={`Remove ${fileName}`}
                className="flex-shrink-0 hover:text-destructive transition-colors"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Attach button */}
      <div className="flex items-center gap-2">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileChange}
          aria-label="Attach files to step"
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={handleAttachClick}
          disabled={isUploading}
          className="h-6 px-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          {isUploading ? (
            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
          ) : (
            <Paperclip className="h-3 w-3 mr-1" />
          )}
          Attach
        </Button>
        {uploadError && (
          <span className="text-xs text-red-500">{uploadError}</span>
        )}
      </div>
    </div>
  );
}

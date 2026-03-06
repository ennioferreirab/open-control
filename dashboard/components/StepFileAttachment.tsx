"use client";

import { useRef, useState } from "react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";
import { Button } from "@/components/ui/button";
import { Loader2, Paperclip } from "lucide-react";
import { FileChip } from "./FileChip";

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

      await addTaskFiles({
        taskId: taskId as Id<"tasks">,
        files: uploadedFiles,
      });

      const newFileNames: string[] = uploadedFiles.map(
        (f: { name: string }) => f.name
      );
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

  return (
    <div className="mt-2 space-y-1">
      {attachedFiles.length > 0 && (
        <div className="flex flex-col gap-0.5">
          {attachedFiles.map((fileName) => (
            <FileChip
              key={fileName}
              name={fileName}
              onRemove={() => onFileRemoved(stepTempId, fileName)}
            />
          ))}
        </div>
      )}

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

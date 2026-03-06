"use client";

import { useState, useRef, useCallback } from "react";
import { useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Id } from "../convex/_generated/dataModel";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_FILES_PER_BATCH = 5;

export interface UploadedFile {
  name: string;
  type: string;
  size: number;
  subfolder: string;
  uploadedAt: string;
}

export interface PendingFile {
  file: File;
  name: string;
  size: number;
  type: string;
}

export function useFileUpload(taskId: string) {
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const addTaskFiles = useMutation(api.tasks.addTaskFiles);

  const addFiles = useCallback((files: FileList | File[]) => {
    const fileArray = Array.from(files);
    setUploadError("");

    const errors: string[] = [];
    const valid: PendingFile[] = [];

    for (const file of fileArray) {
      if (file.size > MAX_FILE_SIZE) {
        errors.push(`"${file.name}" exceeds 10MB limit`);
        continue;
      }
      valid.push({ file, name: file.name, size: file.size, type: file.type });
    }

    setPendingFiles((prev) => {
      const combined = [...prev, ...valid];
      if (combined.length > MAX_FILES_PER_BATCH) {
        errors.push(`Max ${MAX_FILES_PER_BATCH} files per message`);
        return combined.slice(0, MAX_FILES_PER_BATCH);
      }
      return combined;
    });

    if (errors.length > 0) {
      setUploadError(errors.join(". "));
    }
  }, []);

  const removePendingFile = useCallback((name: string) => {
    setPendingFiles((prev) => prev.filter((f) => f.name !== name));
    setUploadError("");
  }, []);

  const uploadAll = useCallback(async (): Promise<UploadedFile[]> => {
    if (pendingFiles.length === 0) return [];

    setIsUploading(true);
    setUploadError("");

    try {
      const formData = new FormData();
      for (const pf of pendingFiles) {
        formData.append("files", pf.file, pf.name);
      }

      const res = await fetch(`/api/tasks/${taskId}/files`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `Upload failed: ${res.status}`);
      }

      const { files: uploadedFiles } = await res.json();

      // Register at task level (Files tab)
      await addTaskFiles({
        taskId: taskId as Id<"tasks">,
        files: uploadedFiles,
      });

      setPendingFiles([]);
      return uploadedFiles;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setUploadError(msg);
      throw err;
    } finally {
      setIsUploading(false);
    }
  }, [pendingFiles, taskId, addTaskFiles]);

  const openFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const clearPending = useCallback(() => {
    setPendingFiles([]);
    setUploadError("");
  }, []);

  return {
    pendingFiles,
    isUploading,
    uploadError,
    fileInputRef,
    addFiles,
    removePendingFile,
    uploadAll,
    openFilePicker,
    clearPending,
  };
}

"use client";

import { useEffect, useMemo, useState } from "react";

interface FileRef {
  name: string;
  subfolder: string;
}

interface FetchState {
  requestKey: string | null;
  content: string | null;
  blobUrl: string | null;
  error: string | null;
}

interface FetchResult {
  content: string | null;
  blobUrl: string | null;
  loading: boolean;
  error: string | null;
}

const BINARY_EXTS = new Set(["pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "ico", "svg"]);

const INITIAL_STATE: FetchState = {
  requestKey: null,
  content: null,
  blobUrl: null,
  error: null,
};

function isBinary(filename: string): boolean {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return BINARY_EXTS.has(ext);
}

function getRequestKey(taskId: string, file: FileRef | null): string | null {
  if (!file) {
    return null;
  }

  return `${taskId}:${file.subfolder}:${file.name}`;
}

export function useDocumentFetch(taskId: string, file: FileRef | null): FetchResult {
  const [state, setState] = useState<FetchState>(INITIAL_STATE);
  const requestKey = useMemo(() => getRequestKey(taskId, file), [taskId, file]);

  useEffect(() => {
    if (!file || !requestKey) {
      return;
    }

    const controller = new AbortController();
    let isActive = true;
    let createdObjectUrl: string | null = null;

    const load = async () => {
      try {
        const url = `/api/tasks/${taskId}/files/${file.subfolder}/${encodeURIComponent(file.name)}`;
        const response = await fetch(url, { signal: controller.signal });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        let nextContent: string | null = null;
        if (isBinary(file.name)) {
          const blob = await response.blob();
          createdObjectUrl = URL.createObjectURL(blob);
        } else {
          nextContent = await response.text();
        }

        if (!isActive) {
          if (createdObjectUrl) {
            URL.revokeObjectURL(createdObjectUrl);
          }
          return;
        }

        setState({
          requestKey,
          content: nextContent,
          blobUrl: createdObjectUrl,
          error: null,
        });
      } catch (error) {
        if (!isActive || controller.signal.aborted) {
          return;
        }

        setState({
          requestKey,
          content: null,
          blobUrl: null,
          error: error instanceof Error ? error.message : "Failed to load file",
        });
      }
    };

    void load();

    return () => {
      isActive = false;
      controller.abort();
      if (createdObjectUrl) {
        URL.revokeObjectURL(createdObjectUrl);
      }
    };
  }, [file, requestKey, taskId]);

  if (!file || !requestKey) {
    return {
      content: null,
      blobUrl: null,
      loading: false,
      error: null,
    };
  }

  const isResolvedForCurrentFile = state.requestKey === requestKey;
  return {
    content: isResolvedForCurrentFile ? state.content : null,
    blobUrl: isResolvedForCurrentFile ? state.blobUrl : null,
    loading: !isResolvedForCurrentFile,
    error: isResolvedForCurrentFile ? state.error : null,
  };
}

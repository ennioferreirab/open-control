"use client";
import { useState, useEffect } from "react";

interface FileRef {
  name: string;
  subfolder: string;
}

interface FetchResult {
  content: string | null;
  blobUrl: string | null;
  loading: boolean;
  error: string | null;
}

const BINARY_EXTS = new Set(["pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "ico", "svg"]);

function isBinary(filename: string): boolean {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return BINARY_EXTS.has(ext);
}

export function useDocumentFetch(taskId: string, file: FileRef | null): FetchResult {
  const [content, setContent] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setContent(null);
      setBlobUrl(null);
      setError(null);
      return;
    }

    let objectUrl: string | null = null;
    setLoading(true);
    setContent(null);
    setBlobUrl(null);
    setError(null);

    const url = `/api/tasks/${taskId}/files/${file.subfolder}/${encodeURIComponent(file.name)}`;

    fetch(url)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (isBinary(file.name)) {
          const blob = await res.blob();
          objectUrl = URL.createObjectURL(blob);
          setBlobUrl(objectUrl);
        } else {
          const text = await res.text();
          setContent(text);
        }
      })
      .catch((err) => setError(err.message ?? "Failed to load file"))
      .finally(() => setLoading(false));

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [taskId, file?.name, file?.subfolder]);

  return { content, blobUrl, loading, error };
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";

interface SkillFile {
  path: string;
  isDirectory: boolean;
}

function encodeFilePath(filePath: string): string {
  return filePath.split("/").map(encodeURIComponent).join("/");
}

export function useSkillDetail(skillName: string | null) {
  const skill = useQuery(api.skills.getByName, skillName ? { name: skillName } : "skip");
  const [files, setFiles] = useState<SkillFile[] | null>(null);
  const [filesLoading, setFilesLoading] = useState(false);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  // Load file listing when skill opens
  useEffect(() => {
    if (!skillName) {
      setFiles(null);
      setFileContent(null);
      setSelectedFile(null);
      setSaveError(null);
      return;
    }

    let cancelled = false;
    setFilesLoading(true);

    fetch(`/api/skills/${encodeURIComponent(skillName)}/files`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error("Failed to load files"))))
      .then((data: { files: SkillFile[] }) => {
        if (cancelled) return;
        setFiles(data.files);
        setFilesLoading(false);
        // Auto-select SKILL.md if present
        const skillMd = data.files.find((f) => f.path === "SKILL.md");
        if (skillMd) {
          setSelectedFile("SKILL.md");
        } else if (data.files.length > 0) {
          const firstFile = data.files.find((f) => !f.isDirectory);
          if (firstFile) setSelectedFile(firstFile.path);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setFiles([]);
        setFilesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [skillName]);

  // Load file content when selection changes
  useEffect(() => {
    if (!skillName || !selectedFile) {
      setFileContent(null);
      return;
    }

    let cancelled = false;
    setFileLoading(true);

    fetch(`/api/skills/${encodeURIComponent(skillName)}/files/${encodeFilePath(selectedFile)}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error("Failed to load file"))))
      .then((data: { content: string }) => {
        if (cancelled) return;
        setFileContent(data.content);
        setFileLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setFileContent(null);
        setFileLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [skillName, selectedFile]);

  const saveFile = useCallback(
    async (filePath: string, content: string) => {
      if (!skillName) return;
      setSaving(true);
      setSaveError(null);
      try {
        const res = await fetch(
          `/api/skills/${encodeURIComponent(skillName)}/files/${encodeFilePath(filePath)}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content }),
          },
        );
        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: "Failed to save" }));
          throw new Error(err.error);
        }
        // Refresh content after save
        setFileContent(content);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to save file";
        setSaveError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [skillName],
  );

  const clearError = useCallback(() => setSaveError(null), []);

  return {
    skill: skill ?? null,
    isLoading: skill === undefined,
    files,
    filesLoading,
    selectedFile,
    setSelectedFile,
    fileContent,
    fileLoading,
    saving,
    saveError,
    saveFile,
    clearError,
  };
}

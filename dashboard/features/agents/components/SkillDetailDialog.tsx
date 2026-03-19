"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MarkdownViewer } from "@/components/viewers/MarkdownViewer";
import { File, Folder, Pencil, Save, X, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSkillDetail } from "@/features/agents/hooks/useSkillDetail";

interface SkillDetailDialogProps {
  skillName: string | null;
  onClose: () => void;
}

/** Count the number of `/` in a path to determine nesting depth. */
function depthOf(path: string): number {
  return (path.match(/\//g) ?? []).length;
}

/** Get the display name (last segment) of a path. */
function displayName(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1];
}

export function SkillDetailDialog({ skillName, onClose }: SkillDetailDialogProps) {
  const {
    skill,
    isLoading,
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
  } = useSkillDetail(skillName);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!skillName) {
      setEditing(false);
      setSaved(false);
    }
  }, [skillName]);

  // Reset edit state when switching files
  useEffect(() => {
    setEditing(false);
    setSaved(false);
    clearError();
  }, [selectedFile, clearError]);

  const handleSelectFile = useCallback(
    (path: string) => {
      if (editing) {
        if (!window.confirm("You have unsaved changes. Discard them?")) return;
      }
      setSelectedFile(path);
    },
    [editing, setSelectedFile],
  );

  const handleEdit = () => {
    if (fileContent !== null) {
      setDraft(fileContent);
      setEditing(true);
      setSaved(false);
      clearError();
    }
  };

  const handleCancel = () => {
    setEditing(false);
    clearError();
  };

  const handleSave = async () => {
    if (!selectedFile) return;
    try {
      await saveFile(selectedFile, draft);
      setEditing(false);
      setSaved(true);
    } catch {
      // Error captured in saveError via hook
    }
  };

  const isMarkdown = selectedFile?.endsWith(".md");

  return (
    <Dialog open={!!skillName} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[70vw] h-[90vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b shrink-0">
          <div className="flex items-center justify-between pr-8">
            <div>
              <DialogTitle>{skillName}</DialogTitle>
              <DialogDescription>
                {skill?.description ?? (isLoading ? "Loading..." : "Skill not found")}
              </DialogDescription>
            </div>
            <div className="flex items-center gap-2">
              {selectedFile && !editing && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleEdit}
                  disabled={fileLoading || fileContent === null}
                >
                  <Pencil className="h-3.5 w-3.5 mr-1.5" />
                  Edit
                </Button>
              )}
              {editing && (
                <>
                  <Button variant="ghost" size="sm" onClick={handleCancel} disabled={saving}>
                    <X className="h-3.5 w-3.5 mr-1.5" />
                    Cancel
                  </Button>
                  <Button size="sm" onClick={handleSave} disabled={saving}>
                    <Save className="h-3.5 w-3.5 mr-1.5" />
                    {saving ? "Saving..." : "Save"}
                  </Button>
                </>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="flex flex-1 min-h-0">
          {/* File tree sidebar */}
          <div className="w-56 shrink-0 border-r">
            <ScrollArea className="h-full">
              <div className="p-2">
                {filesLoading ? (
                  <p className="text-xs text-muted-foreground px-2 py-4">Loading files...</p>
                ) : files && files.length > 0 ? (
                  files.map((f) => {
                    const depth = depthOf(f.path);
                    const indent = depth * 12;
                    return f.isDirectory ? (
                      <div
                        key={f.path}
                        className="flex items-center gap-1.5 px-2 py-1 text-xs text-muted-foreground"
                        style={{ paddingLeft: `${8 + indent}px` }}
                      >
                        <Folder className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{displayName(f.path)}</span>
                      </div>
                    ) : (
                      <button
                        key={f.path}
                        type="button"
                        onClick={() => handleSelectFile(f.path)}
                        className={cn(
                          "flex w-full items-center gap-1.5 rounded py-1 text-xs text-left transition-colors",
                          selectedFile === f.path
                            ? "bg-accent text-accent-foreground font-medium"
                            : "hover:bg-muted/50 text-muted-foreground",
                        )}
                        style={{ paddingLeft: `${8 + indent}px` }}
                      >
                        <File className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{displayName(f.path)}</span>
                      </button>
                    );
                  })
                ) : (
                  <p className="text-xs text-muted-foreground px-2 py-4">No files found</p>
                )}
              </div>
            </ScrollArea>
          </div>

          {/* File content area */}
          <div className="flex-1 min-w-0 overflow-hidden">
            {fileLoading ? (
              <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                Loading...
              </div>
            ) : !selectedFile ? (
              <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                Select a file
              </div>
            ) : editing ? (
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="h-full w-full resize-none border-0 bg-background px-6 py-4 font-mono text-sm outline-none"
              />
            ) : fileContent !== null ? (
              <div className="h-full overflow-auto">
                {isMarkdown ? (
                  <MarkdownViewer content={fileContent} />
                ) : (
                  <pre className="px-6 py-4 font-mono text-sm whitespace-pre-wrap break-words select-text">
                    {fileContent}
                  </pre>
                )}
              </div>
            ) : null}
          </div>
        </div>

        {saveError && (
          <div className="flex items-center gap-2 px-6 py-3 border-t bg-red-500/10 text-red-700 dark:text-red-400 text-sm shrink-0">
            <span>Failed to save: {saveError}</span>
          </div>
        )}

        {saved && !saveError && (
          <div className="flex items-center gap-2 px-6 py-3 border-t bg-amber-500/10 text-amber-700 dark:text-amber-400 text-sm shrink-0">
            <Terminal className="h-4 w-4 shrink-0" />
            <span>
              Saved to disk. Run{" "}
              <code className="font-mono bg-muted px-1.5 py-0.5 rounded text-xs">mc sync</code> to
              update the database.
            </span>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

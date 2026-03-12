"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Download, Minus, Plus, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useDocumentFetch } from "@/hooks/useDocumentFetch";
const PdfViewer = dynamic(() => import("@/components/viewers/PdfViewer").then(m => m.PdfViewer), { ssr: false });
import { MarkdownViewer } from "@/components/viewers/MarkdownViewer";
import { HtmlViewer } from "@/components/viewers/HtmlViewer";
import { ImageViewer } from "@/components/viewers/ImageViewer";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

interface FileRef {
  name: string;
  type: string;
  size: number;
  subfolder: string;
}

interface Props {
  taskId: string;
  file: FileRef | null;
  onClose: () => void;
}

const TEXT_EXTS = new Set(["txt", "csv", "log", "json", "xml", "yaml", "yml"]);
const CODE_EXTS = new Set(["py","ts","tsx","js","jsx","java","go","rs","rb","php","c","cpp","h","css","scss","sql","sh","bash","zsh","swift","kt"]);
const MD_EXTS = new Set(["md", "markdown"]);
const HTML_EXTS = new Set(["html", "htm"]);
const IMAGE_EXTS = new Set(["png","jpg","jpeg","gif","svg","webp","bmp","ico"]);

const LANG_MAP: Record<string, string> = {
  py: "python", ts: "typescript", tsx: "tsx", js: "javascript", jsx: "jsx",
  java: "java", go: "go", rs: "rust", rb: "ruby", php: "php",
  c: "c", cpp: "cpp", h: "c", css: "css", scss: "scss",
  sql: "sql", sh: "bash", bash: "bash", zsh: "bash", swift: "swift", kt: "kotlin",
};

function getExt(name: string) {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

function formatSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(0)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getViewerType(name: string): "text" | "code" | "markdown" | "html" | "image" | "pdf" | "unsupported" {
  const ext = getExt(name);
  if (ext === "pdf") return "pdf";
  if (IMAGE_EXTS.has(ext)) return "image";
  if (CODE_EXTS.has(ext)) return "code";
  if (MD_EXTS.has(ext)) return "markdown";
  if (HTML_EXTS.has(ext)) return "html";
  if (TEXT_EXTS.has(ext)) return "text";
  return "unsupported";
}

export function DocumentViewerModal({ taskId, file, onClose }: Props) {
  const [fontSize, setFontSize] = useState(14);
  const { content, blobUrl, loading, error } = useDocumentFetch(taskId, file);

  const handleDownload = () => {
    if (!file) return;
    const a = document.createElement("a");
    a.href = `/api/tasks/${taskId}/files/${file.subfolder}/${encodeURIComponent(file.name)}`;
    a.download = file.name;
    a.click();
  };

  const viewerType = file ? getViewerType(file.name) : "unsupported";
  const ext = file ? getExt(file.name) : "";

  const renderContent = () => {
    if (loading) return <div className="flex items-center justify-center h-full text-muted-foreground text-sm">Loading...</div>;
    if (error) return <div className="flex items-center justify-center h-full text-red-500 text-sm">Error: {error}</div>;

    if (viewerType === "text") {
      return (
        <div className="h-full flex flex-col">
          <div className="flex items-center gap-1 px-4 py-2 border-b">
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setFontSize(s => Math.max(10, s - 2))}><Minus className="h-3 w-3" /></Button>
            <span className="text-xs text-muted-foreground w-8 text-center">{fontSize}px</span>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setFontSize(s => Math.min(24, s + 2))}><Plus className="h-3 w-3" /></Button>
          </div>
          <pre className="flex-1 overflow-auto p-4 font-mono whitespace-pre-wrap break-all" style={{ fontSize }}>{content}</pre>
        </div>
      );
    }

    if (viewerType === "code") {
      return (
        <div className="h-full flex flex-col">
          <div className="flex items-center gap-1 px-4 py-2 border-b">
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setFontSize(s => Math.max(10, s - 2))}><Minus className="h-3 w-3" /></Button>
            <span className="text-xs text-muted-foreground w-8 text-center">{fontSize}px</span>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setFontSize(s => Math.min(24, s + 2))}><Plus className="h-3 w-3" /></Button>
          </div>
          <div className="flex-1 overflow-auto" style={{ fontSize }}>
            <SyntaxHighlighter
              language={LANG_MAP[ext] ?? "text"}
              style={vscDarkPlus}
              showLineNumbers
              wrapLongLines={false}
              customStyle={{ margin: 0, height: "100%", borderRadius: 0, fontSize: "inherit" }}
            >
              {content ?? ""}
            </SyntaxHighlighter>
          </div>
        </div>
      );
    }

    if (viewerType === "pdf") {
      return <PdfViewer blobUrl={blobUrl!} onDownload={handleDownload} />;
    }

    if (viewerType === "markdown") {
      return (
        <MarkdownViewer
          content={content ?? ""}
          taskId={taskId}
          sourceFile={file ? { name: file.name, subfolder: file.subfolder } : undefined}
        />
      );
    }

    if (viewerType === "html") {
      return <HtmlViewer content={content ?? ""} />;
    }

    if (viewerType === "image") {
      return <ImageViewer blobUrl={blobUrl!} filename={file!.name} onDownload={handleDownload} />;
    }

    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
        <p className="text-sm">Preview not available for this file type.</p>
        <Button variant="outline" size="sm" onClick={handleDownload}><Download className="h-3.5 w-3.5 mr-1.5" />Download</Button>
      </div>
    );
  };

  return (
    <Dialog open={file !== null} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-4xl w-full h-[80vh] flex flex-col p-0 gap-0 [&>button]:hidden">
        <DialogHeader className="flex flex-row items-center justify-between px-6 py-4 border-b shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <DialogTitle className="text-base font-medium truncate">{file?.name}</DialogTitle>
            <DialogDescription className="sr-only">
              {file ? `Preview and download ${file.name}` : "Preview the selected file"}
            </DialogDescription>
            {file && <Badge variant="secondary" className="text-xs flex-shrink-0">{getExt(file.name).toUpperCase()}</Badge>}
            {file && <span className="text-xs text-muted-foreground flex-shrink-0">{formatSize(file.size)}</span>}
          </div>
          <div className="flex items-center gap-1 shrink-0 ml-4">
            <Button variant="ghost" size="sm" onClick={handleDownload}>
              <Download className="h-3.5 w-3.5 mr-1.5" />Download
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DialogHeader>
        <div className="flex-1 min-h-0 overflow-hidden">
          {renderContent()}
        </div>
      </DialogContent>
    </Dialog>
  );
}

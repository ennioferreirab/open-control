"use client";

import { useEffect, useCallback, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChevronLeft, ChevronRight, Download, FileText, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useDocumentFetch } from "@/hooks/useDocumentFetch";
import {
  buildDocumentUrl,
  resolveDocumentSource,
  type DocumentFileRef,
  type DocumentSource,
} from "@/lib/documentSources";
const PdfViewer = dynamic(() => import("@/components/viewers/PdfViewer").then((m) => m.PdfViewer), {
  ssr: false,
});
import { MarkdownViewer } from "@/components/viewers/MarkdownViewer";
import { HtmlViewer } from "@/components/viewers/HtmlViewer";
import { ImageViewer } from "@/components/viewers/ImageViewer";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

interface Props {
  taskId?: string;
  source?: DocumentSource;
  file: DocumentFileRef | null;
  files?: DocumentFileRef[];
  onNavigate?: (file: DocumentFileRef) => void;
  onClose: () => void;
}

const TEXT_EXTS = new Set(["txt", "csv", "log", "json", "xml", "yaml", "yml"]);
const CODE_EXTS = new Set([
  "py",
  "ts",
  "tsx",
  "js",
  "jsx",
  "java",
  "go",
  "rs",
  "rb",
  "php",
  "c",
  "cpp",
  "h",
  "css",
  "scss",
  "sql",
  "sh",
  "bash",
  "zsh",
  "swift",
  "kt",
]);
const MD_EXTS = new Set(["md", "markdown"]);
const HTML_EXTS = new Set(["html", "htm"]);
const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "ico"]);

const LANG_MAP: Record<string, string> = {
  py: "python",
  ts: "typescript",
  tsx: "tsx",
  js: "javascript",
  jsx: "jsx",
  java: "java",
  go: "go",
  rs: "rust",
  rb: "ruby",
  php: "php",
  c: "c",
  cpp: "cpp",
  h: "c",
  css: "css",
  scss: "scss",
  sql: "sql",
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  swift: "swift",
  kt: "kotlin",
};

function getExt(name: string) {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

/** Abbreviate parent dirs to first char: "reports/deep/file.txt" → "r/d/file.txt" */
function abbreviatePath(name: string): string {
  const parts = name.split("/");
  if (parts.length <= 1) return name;
  const fileName = parts[parts.length - 1];
  const abbreviated = parts.slice(0, -1).map((p) => (p.length > 0 ? p[0] : ""));
  return [...abbreviated, fileName].join("/");
}

function getViewerType(
  name: string,
): "text" | "code" | "markdown" | "html" | "image" | "pdf" | "unsupported" {
  const ext = getExt(name);
  if (ext === "pdf") return "pdf";
  if (IMAGE_EXTS.has(ext)) return "image";
  if (CODE_EXTS.has(ext)) return "code";
  if (MD_EXTS.has(ext)) return "markdown";
  if (HTML_EXTS.has(ext)) return "html";
  if (TEXT_EXTS.has(ext)) return "text";
  return "unsupported";
}

function getFileKey(f: DocumentFileRef): string {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sourceTaskId = (f as any).sourceTaskId ?? "local";
  return `${sourceTaskId}:${f.subfolder}:${f.name}`;
}

export function DocumentViewerModal({ taskId, source, file, files, onNavigate, onClose }: Props) {
  const resolvedSource = resolveDocumentSource(source, taskId);
  const { content, blobUrl, loading, error } = useDocumentFetch(
    resolvedSource ?? source ?? { kind: "task", taskId: taskId ?? "" },
    file,
  );

  const currentIndex = useMemo(() => {
    if (!file || !files?.length) return -1;
    const key = getFileKey(file);
    return files.findIndex((f) => getFileKey(f) === key);
  }, [file, files]);

  const hasPrev = currentIndex > 0;
  const hasNext = files ? currentIndex < files.length - 1 : false;

  const goPrev = useCallback(() => {
    if (hasPrev && files && onNavigate) onNavigate(files[currentIndex - 1]);
  }, [hasPrev, files, onNavigate, currentIndex]);

  const goNext = useCallback(() => {
    if (hasNext && files && onNavigate) onNavigate(files[currentIndex + 1]);
  }, [hasNext, files, onNavigate, currentIndex]);

  useEffect(() => {
    if (!file) return;
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        goNext();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [file, goPrev, goNext]);

  const handleDownload = () => {
    if (!file || !resolvedSource) return;
    const a = document.createElement("a");
    a.href = buildDocumentUrl(resolvedSource, file);
    a.download = file.name;
    a.click();
  };

  const handlePrintPdf = () => {
    const rendered = document.querySelector("[data-md-print-content]");
    if (!rendered) return;
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    const title = file?.name?.replace(/\.(md|markdown)$/i, "") ?? "document";
    printWindow.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${title}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    max-width: 800px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; font-size: 14px; line-height: 1.7; }
  h1 { font-size: 28px; font-weight: 700; margin: 32px 0 12px; border-bottom: 1px solid #e5e5e5; padding-bottom: 4px; }
  h2 { font-size: 22px; font-weight: 600; margin: 28px 0 8px; }
  h3 { font-size: 18px; font-weight: 600; margin: 24px 0 8px; }
  h4, h5, h6 { font-size: 15px; font-weight: 600; margin: 20px 0 4px; }
  p { margin: 0 0 8px; }
  ul, ol { margin: 0 0 8px; padding-left: 20px; }
  li { margin: 2px 0; }
  code { font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
  pre { background: #f4f4f4; padding: 16px; border-radius: 6px; overflow-x: auto;
    font-size: 13px; line-height: 1.5; margin: 8px 0; }
  pre code { background: none; padding: 0; }
  blockquote { border-left: 4px solid #e5e5e5; padding-left: 12px; margin: 8px 0; color: #666; font-style: italic; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
  th, td { padding: 8px 12px; border: 1px solid #e5e5e5; text-align: left; }
  th { background: #f9f9f9; font-weight: 600; }
  hr { border: none; border-top: 1px solid #e5e5e5; margin: 16px 0; }
  img { max-width: 100%; height: auto; border-radius: 4px; margin: 8px 0; }
  a { color: #2563eb; text-decoration: none; }
  strong { font-weight: 600; }
  @media print {
    body { margin: 0; padding: 20px; }
    pre { white-space: pre-wrap; word-wrap: break-word; }
    a { color: #1a1a1a; }
    img { break-inside: avoid; }
    h1, h2, h3, h4, h5, h6 { break-after: avoid; }
  }
</style></head><body>${rendered.innerHTML}</body></html>`);
    printWindow.document.close();
    printWindow.addEventListener("afterprint", () => printWindow.close());
    // Small delay to ensure images load before print dialog
    setTimeout(() => printWindow.print(), 300);
  };

  const viewerType = file ? getViewerType(file.name) : "unsupported";
  const ext = file ? getExt(file.name) : "";

  const renderContent = () => {
    if (loading)
      return (
        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
          Loading...
        </div>
      );
    if (error)
      return (
        <div className="flex items-center justify-center h-full text-red-500 text-sm">
          Error: {error}
        </div>
      );

    if (viewerType === "text") {
      return (
        <pre className="h-full overflow-auto p-4 font-mono text-sm whitespace-pre-wrap break-all">
          {content}
        </pre>
      );
    }

    if (viewerType === "code") {
      return (
        <div className="h-full overflow-auto text-sm">
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
          source={resolvedSource ?? undefined}
          sourceFile={file ?? undefined}
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
        <Button variant="outline" size="sm" onClick={handleDownload}>
          <Download className="h-3.5 w-3.5 mr-1.5" />
          Download
        </Button>
      </div>
    );
  };

  const showNav = files && files.length > 1;

  return (
    <Dialog
      open={file !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="max-w-4xl w-full h-[80vh] flex flex-col p-0 gap-0 [&>button]:hidden">
        <DialogHeader className="flex flex-row items-center px-4 py-3 border-b shrink-0 gap-2">
          {/* Left: navigation */}
          {showNav ? (
            <div className="flex items-center gap-0.5 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label="Previous file"
                disabled={!hasPrev}
                onClick={goPrev}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground min-w-[40px] text-center tabular-nums">
                {currentIndex + 1} / {files.length}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label="Next file"
                disabled={!hasNext}
                onClick={goNext}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          ) : null}

          {/* Center: path + badge */}
          <div className="flex-1 flex items-center justify-center gap-2 min-w-0">
            <DialogTitle className="text-sm font-medium truncate">
              {file ? abbreviatePath(file.name) : ""}
            </DialogTitle>
            <DialogDescription className="sr-only">
              {file ? `Preview and download ${file.name}` : "Preview the selected file"}
            </DialogDescription>
            {file && (
              <Badge variant="secondary" className="text-xs flex-shrink-0">
                {getExt(file.name).toUpperCase()}
              </Badge>
            )}
          </div>

          {/* Right: actions */}
          <div className="flex items-center gap-1 shrink-0">
            {viewerType === "markdown" && (
              <Button variant="ghost" size="sm" onClick={handlePrintPdf}>
                <FileText className="h-3.5 w-3.5 mr-1.5" />
                Save as PDF
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={handleDownload}>
              <Download className="h-3.5 w-3.5 mr-1.5" />
              Download
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DialogHeader>
        <div className="flex-1 min-h-0 overflow-hidden">{renderContent()}</div>
      </DialogContent>
    </Dialog>
  );
}

"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/button";

interface MarkdownSourceFile {
  name: string;
  subfolder: string;
}

interface MarkdownViewerProps {
  content: string;
  taskId?: string;
  sourceFile?: MarkdownSourceFile;
}

function isRelativeMarkdownPath(value: string): boolean {
  if (!value || value.startsWith("#") || value.startsWith("/") || value.startsWith("//")) {
    return false;
  }

  return !/^[a-zA-Z][a-zA-Z\d+.-]*:/.test(value);
}

function splitMarkdownPath(value: string): { pathname: string; suffix: string } {
  const suffixIndex = value.search(/[?#]/);
  if (suffixIndex === -1) {
    return { pathname: value, suffix: "" };
  }

  return {
    pathname: value.slice(0, suffixIndex),
    suffix: value.slice(suffixIndex),
  };
}

function normalizeTaskPath(sourceName: string, relativePath: string): string | null {
  const resolved = sourceName.split("/").filter(Boolean);
  resolved.pop();

  for (const segment of relativePath.split("/")) {
    if (!segment || segment === ".") {
      continue;
    }
    if (segment === "..") {
      if (resolved.length === 0) {
        return null;
      }
      resolved.pop();
      continue;
    }
    resolved.push(segment);
  }

  return resolved.join("/");
}

function buildTaskFileUrl(taskId: string | undefined, sourceFile: MarkdownSourceFile | undefined, value: string | undefined): string | undefined {
  if (!value || !taskId || !sourceFile || !isRelativeMarkdownPath(value)) {
    return value;
  }

  const { pathname, suffix } = splitMarkdownPath(value);
  const normalizedPath = normalizeTaskPath(sourceFile.name, pathname);
  if (!normalizedPath) {
    return undefined;
  }

  return `/api/tasks/${taskId}/files/${sourceFile.subfolder}/${encodeURIComponent(normalizedPath)}${suffix}`;
}

export function MarkdownViewer({ content, taskId, sourceFile }: MarkdownViewerProps) {
  const [mode, setMode] = useState<"rendered" | "raw">("rendered");
  const resolveTaskUrl = (value: string | undefined) => buildTaskFileUrl(taskId, sourceFile, value);

  return (
    <div className="flex h-full min-w-0 max-w-full flex-col">
      <div className="flex items-center gap-2 px-4 py-2 border-b shrink-0">
        <Button variant={mode === "rendered" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("rendered")}>Rendered</Button>
        <Button variant={mode === "raw" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("raw")}>Raw</Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-6">
        {mode === "rendered" ? (
          <div className="w-full min-w-0 max-w-full select-text text-sm leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code(props) {
                  const { className, children } = props;
                  const match = /language-(\w+)/.exec(className ?? "");
                  if (match) {
                    return (
                      <SyntaxHighlighter language={match[1]} style={vscDarkPlus} PreTag="div">
                        {String(children).replace(/\n$/, "")}
                      </SyntaxHighlighter>
                    );
                  }
                  return <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">{children}</code>;
                },
                // Prevent double-wrapping: react-markdown wraps fenced code blocks
                // in <pre> by default; our code override already handles the container.
                pre({ children }) {
                  return <>{children}</>;
                },
                a({ href, children }) {
                  const resolvedHref = resolveTaskUrl(href);
                  return (
                    <a
                      href={resolvedHref}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-500 hover:underline"
                    >
                      {children}
                    </a>
                  );
                },
                img({ src, alt }) {
                  const resolvedSrc = resolveTaskUrl(src);
                  return (
                    <img
                      src={resolvedSrc}
                      alt={alt ?? ""}
                      className="max-w-full h-auto rounded-md border border-border my-3"
                    />
                  );
                },
                p({ children }) {
                  return <p className="mb-2 last:mb-0">{children}</p>;
                },
                ul({ children }) {
                  return <ul className="mb-2 pl-5 list-disc space-y-0.5">{children}</ul>;
                },
                ol({ children }) {
                  return <ol className="mb-2 pl-5 list-decimal space-y-0.5">{children}</ol>;
                },
                li({ children }) {
                  return <li>{children}</li>;
                },
                strong({ children }) {
                  return <strong className="font-semibold">{children}</strong>;
                },
                em({ children }) {
                  return <em className="italic">{children}</em>;
                },
                hr() {
                  return <hr className="my-3 border-border" />;
                },
                h1({ children }) {
                  return <h1 className="text-2xl font-bold mb-3 mt-4 first:mt-0 border-b border-border pb-1">{children}</h1>;
                },
                h2({ children }) {
                  return <h2 className="text-xl font-semibold mb-2 mt-4 first:mt-0">{children}</h2>;
                },
                h3({ children }) {
                  return <h3 className="text-lg font-semibold mb-2 mt-3 first:mt-0">{children}</h3>;
                },
                h4({ children }) {
                  return <h4 className="text-base font-semibold mb-1 mt-3 first:mt-0">{children}</h4>;
                },
                h5({ children }) {
                  return <h5 className="text-sm font-semibold mb-1 mt-2 first:mt-0">{children}</h5>;
                },
                h6({ children }) {
                  return <h6 className="text-xs font-semibold mb-1 mt-2 first:mt-0 text-muted-foreground">{children}</h6>;
                },
                table({ children }) {
                  return (
                    <div className="my-3 overflow-x-auto rounded-md border border-border">
                      <table className="w-full text-xs border-collapse">{children}</table>
                    </div>
                  );
                },
                thead({ children }) {
                  return <thead className="bg-muted">{children}</thead>;
                },
                th({ children }) {
                  return (
                    <th className="px-3 py-2 font-medium text-left border-b border-border">
                      {children}
                    </th>
                  );
                },
                td({ children }) {
                  return (
                    <td className="px-3 py-2 border-b border-border [tr:last-child_&]:border-0">
                      {children}
                    </td>
                  );
                },
                blockquote({ children }) {
                  return (
                    <blockquote className="border-l-4 border-border pl-3 my-2 text-muted-foreground italic">
                      {children}
                    </blockquote>
                  );
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        ) : (
          <pre className="select-text font-mono text-sm whitespace-pre-wrap break-all">{content}</pre>
        )}
      </div>
    </div>
  );
}

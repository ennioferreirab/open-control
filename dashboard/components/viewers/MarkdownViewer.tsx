"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/button";
import {
  buildRelativeDocumentUrl,
  type DocumentFileRef,
  type DocumentSource,
} from "@/lib/documentSources";

interface MarkdownViewerProps {
  content: string;
  source?: DocumentSource;
  taskId?: string;
  sourceFile?: DocumentFileRef;
}

export function MarkdownViewer({ content, source, taskId, sourceFile }: MarkdownViewerProps) {
  const [mode, setMode] = useState<"rendered" | "raw">("rendered");
  const resolvedSource = source ?? (taskId ? { kind: "task" as const, taskId } : null);
  const resolveTaskUrl = (value: string | undefined) =>
    buildRelativeDocumentUrl(resolvedSource, sourceFile, value);

  return (
    <div className="flex h-full min-w-0 max-w-full flex-col">
      <div className="flex items-center gap-2 px-4 py-2 border-b shrink-0">
        <Button
          variant={mode === "rendered" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setMode("rendered")}
        >
          Rendered
        </Button>
        <Button
          variant={mode === "raw" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setMode("raw")}
        >
          Raw
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-6">
        {mode === "rendered" ? (
          <div
            className="w-full min-w-0 max-w-full select-text text-sm leading-relaxed"
            data-md-print-content
          >
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
                  return (
                    <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                      {children}
                    </code>
                  );
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
                  const resolvedSrc = typeof src === "string" ? resolveTaskUrl(src) : undefined;
                  return (
                    // This viewer needs raw file/blob URLs from the app API, so next/image
                    // is not a good fit for these dynamic preview payloads.
                    // eslint-disable-next-line @next/next/no-img-element
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
                  return (
                    <h1 className="text-2xl font-bold mb-3 mt-4 first:mt-0 border-b border-border pb-1">
                      {children}
                    </h1>
                  );
                },
                h2({ children }) {
                  return <h2 className="text-xl font-semibold mb-2 mt-4 first:mt-0">{children}</h2>;
                },
                h3({ children }) {
                  return <h3 className="text-lg font-semibold mb-2 mt-3 first:mt-0">{children}</h3>;
                },
                h4({ children }) {
                  return (
                    <h4 className="text-base font-semibold mb-1 mt-3 first:mt-0">{children}</h4>
                  );
                },
                h5({ children }) {
                  return <h5 className="text-sm font-semibold mb-1 mt-2 first:mt-0">{children}</h5>;
                },
                h6({ children }) {
                  return (
                    <h6 className="text-xs font-semibold mb-1 mt-2 first:mt-0 text-muted-foreground">
                      {children}
                    </h6>
                  );
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
          <pre className="select-text font-mono text-sm whitespace-pre-wrap break-all">
            {content}
          </pre>
        )}
      </div>
    </div>
  );
}

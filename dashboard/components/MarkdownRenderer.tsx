"use client";

import { useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { linkifyFilePaths } from "@/lib/filePathLinker";
import { Check, Copy } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

interface CodeBlockProps {
  code: string;
  language?: string;
}

function CodeBlock({ code, language = "text" }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard not available
    }
  };

  return (
    <div className="my-3 first:mt-0 last:mb-0 w-full min-w-0 max-w-full overflow-hidden rounded-md border border-border">
      <div className="flex items-center justify-between px-3 py-1.5 bg-muted text-xs">
        <span className="text-muted-foreground uppercase font-medium tracking-wide text-[10px]">
          {language}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3" />
              <span>Copied!</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <SyntaxHighlighter
        language={language.toLowerCase()}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: "12px",
          lineHeight: "1.5",
          padding: "10px 12px",
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

interface MarkdownRendererProps {
  content: string;
  className?: string;
  validArtifactPaths?: Set<string>;
  onFilePathClick?: (path: string) => void;
}

export function MarkdownRenderer({
  content,
  className = "",
  validArtifactPaths,
  onFilePathClick,
}: MarkdownRendererProps) {
  // Serialize artifact paths for stable useMemo dependency (Set references are unstable)
  const artifactPathsKey = useMemo(
    () => (validArtifactPaths ? [...validArtifactPaths].sort().join("\0") : ""),
    [validArtifactPaths],
  );

  const processed = useMemo(() => {
    const text = content || "";
    if (validArtifactPaths && validArtifactPaths.size > 0) {
      return linkifyFilePaths(text, validArtifactPaths);
    }
    return text;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- artifactPathsKey is a stable serialization of validArtifactPaths
  }, [content, artifactPathsKey]);

  return (
    <div
      className={`w-full min-w-0 max-w-full overflow-x-hidden text-sm leading-relaxed break-words select-text ${className}`}
    >
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className: cls, children, ...props }) {
            const match = /language-(\w+)/.exec(cls || "");
            if (match) {
              return <CodeBlock code={String(children).replace(/\n$/, "")} language={match[1]} />;
            }
            return (
              <code
                className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded text-foreground break-all"
                {...props}
              >
                {children}
              </code>
            );
          },
          pre({ children }) {
            return <>{children}</>;
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
          h1({ children }) {
            return (
              <h1 className="text-base font-semibold mb-2 mt-3 first:mt-0 border-b border-border pb-1">
                {children}
              </h1>
            );
          },
          h2({ children }) {
            return <h2 className="text-sm font-semibold mb-2 mt-3 first:mt-0">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="text-sm font-medium mb-1 mt-2 first:mt-0">{children}</h3>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="border-l-4 border-border pl-3 my-2 text-muted-foreground italic">
                {children}
              </blockquote>
            );
          },
          a({ href, children }) {
            if (href?.startsWith("artifact://")) {
              if (onFilePathClick) {
                const path = decodeURIComponent(
                  href.slice("artifact://".length).replace(/\\([()])/g, "$1"),
                );
                return (
                  <button
                    type="button"
                    className="text-blue-500 hover:underline font-mono text-xs"
                    onClick={() => onFilePathClick(path)}
                  >
                    {children}
                  </button>
                );
              }
              // No click handler — render as plain text, not a broken link
              return <span className="font-mono text-xs">{children}</span>;
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:underline"
              >
                {children}
              </a>
            );
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
              <th className="px-3 py-2 font-medium text-left border-b border-border">{children}</th>
            );
          },
          td({ children }) {
            return (
              <td className="px-3 py-2 border-b border-border [tr:last-child_&]:border-0">
                {children}
              </td>
            );
          },
        }}
      >
        {processed}
      </Markdown>
    </div>
  );
}

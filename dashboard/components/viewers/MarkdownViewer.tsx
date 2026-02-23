"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/button";

export function MarkdownViewer({ content }: { content: string }) {
  const [mode, setMode] = useState<"rendered" | "raw">("rendered");

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-2 border-b shrink-0">
        <Button variant={mode === "rendered" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("rendered")}>Rendered</Button>
        <Button variant={mode === "raw" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("raw")}>Raw</Button>
      </div>
      <div className="flex-1 overflow-auto p-6">
        {mode === "rendered" ? (
          <div className="text-sm leading-relaxed">
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
                  return <code className={className}>{children}</code>;
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        ) : (
          <pre className="font-mono text-sm whitespace-pre-wrap break-all">{content}</pre>
        )}
      </div>
    </div>
  );
}

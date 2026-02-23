"use client";
import { useState } from "react";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/button";

export function HtmlViewer({ content }: { content: string }) {
  const [mode, setMode] = useState<"rendered" | "raw">("rendered");

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-2 border-b shrink-0">
        <Button variant={mode === "rendered" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("rendered")}>Rendered</Button>
        <Button variant={mode === "raw" ? "secondary" : "ghost"} size="sm" onClick={() => setMode("raw")}>Raw</Button>
      </div>
      <div className="flex-1 overflow-hidden">
        {mode === "rendered" ? (
          <iframe
            srcDoc={content}
            sandbox="allow-same-origin"
            className="w-full h-full border-0"
            title="HTML preview"
          />
        ) : (
          <div className="h-full overflow-auto">
            <SyntaxHighlighter language="html" style={vscDarkPlus} showLineNumbers customStyle={{ margin: 0, height: "100%", borderRadius: 0 }}>
              {content}
            </SyntaxHighlighter>
          </div>
        )}
      </div>
    </div>
  );
}

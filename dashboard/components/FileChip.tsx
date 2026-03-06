"use client";

import {
  File,
  FileCode,
  FileText,
  Image,
  X,
} from "lucide-react";

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]);
const CODE_EXTS = new Set([
  ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".sh",
]);

function getFileIconType(name: string): "pdf" | "image" | "code" | "generic" {
  const dotIdx = name.lastIndexOf(".");
  if (dotIdx === -1) return "generic";
  const ext = name.slice(dotIdx).toLowerCase();
  if (ext === ".pdf") return "pdf";
  if (IMAGE_EXTS.has(ext)) return "image";
  if (CODE_EXTS.has(ext)) return "code";
  return "generic";
}

function FileIcon({ name }: { name: string }) {
  const iconType = getFileIconType(name);
  const cls = "h-3 w-3 text-muted-foreground";
  switch (iconType) {
    case "pdf":
      return <FileText className={cls} />;
    case "image":
      return <Image className={cls} />;
    case "code":
      return <FileCode className={cls} />;
    default:
      return <File className={cls} />;
  }
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FileChipProps {
  name: string;
  size?: number;
  onRemove?: () => void;
  href?: string;
}

export function FileChip({ name, size, onRemove, href }: FileChipProps) {
  const content = (
    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <FileIcon name={name} />
      <span className="min-w-0 truncate" title={name}>
        {name}
      </span>
      {size != null && (
        <span className="text-muted-foreground/60 shrink-0">
          {humanSize(size)}
        </span>
      )}
      {onRemove && (
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onRemove();
          }}
          aria-label={`Remove ${name}`}
          className="shrink-0 hover:text-destructive transition-colors"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  );

  if (href) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="hover:underline">
        {content}
      </a>
    );
  }

  return content;
}

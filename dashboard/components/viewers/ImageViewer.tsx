"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Download, Maximize2, Minus, Plus } from "lucide-react";

interface Props {
  blobUrl: string;
  filename: string;
  onDownload: () => void;
}

const SCALES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

export function ImageViewer({ blobUrl, filename, onDownload }: Props) {
  const [scale, setScale] = useState<number | "fit">("fit");
  const [error, setError] = useState(false);

  const zoomIn = () => {
    if (scale === "fit") {
      setScale(1.0);
    } else {
      const idx = SCALES.indexOf(scale);
      if (idx < SCALES.length - 1) setScale(SCALES[idx + 1]);
    }
  };

  const zoomOut = () => {
    if (scale === "fit") return;
    const idx = SCALES.indexOf(scale);
    if (idx > 0) setScale(SCALES[idx - 1]);
    else setScale("fit");
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
        <p className="text-sm">Unable to display this image.</p>
        <Button variant="outline" size="sm" onClick={onDownload}>
          <Download className="h-3.5 w-3.5 mr-1.5" />Download
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Controls */}
      <div className="flex items-center gap-1 px-4 py-2 border-b shrink-0">
        <Button
          variant={scale === "fit" ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setScale("fit")}
        >
          <Maximize2 className="h-3.5 w-3.5 mr-1" />Fit
        </Button>
        <Button
          variant={scale === 1.0 ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setScale(1.0)}
        >
          1:1
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomOut} disabled={scale === "fit"}>
          <Minus className="h-3 w-3" />
        </Button>
        {scale !== "fit" && (
          <span className="text-xs text-muted-foreground w-10 text-center">
            {Math.round((scale as number) * 100)}%
          </span>
        )}
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomIn} disabled={scale === 2.0}>
          <Plus className="h-3 w-3" />
        </Button>
      </div>

      {/* Image area */}
      <div className="flex-1 overflow-auto flex items-center justify-center bg-muted/20 p-4">
        {scale === "fit" ? (
          <img
            src={blobUrl}
            alt={filename}
            className="max-w-full max-h-full object-contain"
            onError={() => setError(true)}
          />
        ) : (
          <img
            src={blobUrl}
            alt={filename}
            style={{ transform: `scale(${scale})`, transformOrigin: "top center" }}
            className="block"
            onError={() => setError(true)}
          />
        )}
      </div>
    </div>
  );
}

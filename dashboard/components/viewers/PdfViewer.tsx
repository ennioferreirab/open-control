"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Minus, Plus, Download, Maximize2 } from "lucide-react";

// Configure worker — use CDN for Next.js compatibility
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface Props {
  blobUrl: string;
  onDownload: () => void;
}

const SCALES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

export function PdfViewer({ blobUrl, onDownload }: Props) {
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale, setScale] = useState<number | "fit">("fit");
  const [loadError, setLoadError] = useState(false);
  const [containerWidth, setContainerWidth] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        // contentRect.width is already the content-box width (padding excluded by ResizeObserver)
        setContainerWidth(entry.contentRect.width);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setCurrentPage(1);
    setLoadError(false);
  }, []);

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
  };

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
        <p className="text-sm">Unable to render this PDF.</p>
        <Button variant="outline" size="sm" onClick={onDownload}>
          <Download className="h-3.5 w-3.5 mr-1.5" />
          Download
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Controls */}
      <div className="flex items-center justify-between px-4 py-2 border-b shrink-0 gap-2">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label="Previous page"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((p) => p - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground min-w-[80px] text-center">
            Page {currentPage} of {numPages || "—"}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label="Next page"
            disabled={currentPage >= numPages}
            onClick={() => setCurrentPage((p) => p + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant={scale === "fit" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setScale("fit")}
          >
            <Maximize2 className="h-3.5 w-3.5 mr-1" />
            Fit
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label="Zoom out"
            onClick={zoomOut}
            disabled={scale === "fit"}
          >
            <Minus className="h-3 w-3" />
          </Button>
          <span className="text-xs text-muted-foreground w-12 text-center">
            {scale === "fit" ? "Fit" : `${Math.round((scale as number) * 100)}%`}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label="Zoom in"
            onClick={zoomIn}
            disabled={scale === 2.0}
          >
            <Plus className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* PDF page */}
      <div ref={containerRef} className="flex-1 overflow-auto flex justify-center py-4 bg-muted/30">
        <Document
          file={blobUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={() => setLoadError(true)}
          loading={<div className="text-sm text-muted-foreground mt-8">Loading PDF...</div>}
        >
          {scale === "fit" ? (
            <Page
              pageNumber={currentPage}
              width={containerWidth ?? undefined}
              renderAnnotationLayer
              renderTextLayer
            />
          ) : (
            <Page
              pageNumber={currentPage}
              scale={scale as number}
              renderAnnotationLayer
              renderTextLayer
            />
          )}
        </Document>
      </div>
    </div>
  );
}

"use client";

import { useState, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Minus, Plus, Download } from "lucide-react";

// Configure worker — use CDN for Next.js compatibility
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface Props {
  blobUrl: string;
  onDownload: () => void;
}

export function PdfViewer({ blobUrl, onDownload }: Props) {
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale, setScale] = useState(1.0);
  const [loadError, setLoadError] = useState(false);

  const SCALES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setCurrentPage(1);
    setLoadError(false);
  }, []);

  const zoomIn = () => {
    const idx = SCALES.indexOf(scale);
    if (idx < SCALES.length - 1) setScale(SCALES[idx + 1]);
  };

  const zoomOut = () => {
    const idx = SCALES.indexOf(scale);
    if (idx > 0) setScale(SCALES[idx - 1]);
  };

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
        <p className="text-sm">Unable to render this PDF.</p>
        <Button variant="outline" size="sm" onClick={onDownload}>
          <Download className="h-3.5 w-3.5 mr-1.5" />Download
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Controls */}
      <div className="flex items-center justify-between px-4 py-2 border-b shrink-0 gap-2">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" disabled={currentPage <= 1} onClick={() => setCurrentPage(p => p - 1)}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground min-w-[80px] text-center">
            Page {currentPage} of {numPages || "—"}
          </span>
          <Button variant="ghost" size="icon" className="h-7 w-7" disabled={currentPage >= numPages} onClick={() => setCurrentPage(p => p + 1)}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomOut} disabled={scale <= 0.5}>
            <Minus className="h-3 w-3" />
          </Button>
          <span className="text-xs text-muted-foreground w-12 text-center">{Math.round(scale * 100)}%</span>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomIn} disabled={scale >= 2.0}>
            <Plus className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* PDF page */}
      <div className="flex-1 overflow-auto flex justify-center py-4 bg-muted/30">
        <Document
          file={blobUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={() => setLoadError(true)}
          loading={<div className="text-sm text-muted-foreground mt-8">Loading PDF...</div>}
        >
          <Page
            pageNumber={currentPage}
            scale={scale}
            renderAnnotationLayer
            renderTextLayer
          />
        </Document>
      </div>
    </div>
  );
}

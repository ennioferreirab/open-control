import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

// Mock useDocumentFetch hook
vi.mock("@/hooks/useDocumentFetch", () => ({
  useDocumentFetch: vi.fn(),
}));

// Mock next/dynamic — render PdfViewer as a stub
vi.mock("next/dynamic", () => ({
  default: (_fn: unknown, _opts: unknown) => {
    const Stub = () => <div data-testid="pdf-viewer-stub">PDF Viewer</div>;
    Stub.displayName = "DynamicPdfViewer";
    return Stub;
  },
}));

// Mock react-syntax-highlighter (heavy dep — verify props only)
vi.mock("react-syntax-highlighter", () => ({
  default: ({
    children,
    language,
    showLineNumbers,
  }: {
    children: React.ReactNode;
    language?: string;
    showLineNumbers?: boolean;
    style?: unknown;
    wrapLongLines?: boolean;
    customStyle?: unknown;
  }) => (
    <div
      data-testid="syntax-highlighter"
      data-language={language}
      data-show-line-numbers={String(showLineNumbers)}
    >
      {children}
    </div>
  ),
}));

vi.mock("react-syntax-highlighter/dist/esm/styles/prism", () => ({
  vscDarkPlus: {},
}));

// Mock viewer sub-components
vi.mock("@/components/viewers/MarkdownViewer", () => ({
  MarkdownViewer: ({
    content,
    taskId,
    sourceFile,
  }: {
    content: string;
    taskId?: string;
    sourceFile?: { name: string; subfolder: string };
  }) => (
    <div
      data-testid="markdown-viewer"
      data-task-id={taskId}
      data-source-name={sourceFile?.name}
      data-source-subfolder={sourceFile?.subfolder}
    >
      {content}
    </div>
  ),
}));

vi.mock("@/components/viewers/HtmlViewer", () => ({
  HtmlViewer: ({ content }: { content: string }) => (
    <div data-testid="html-viewer">{content}</div>
  ),
}));

vi.mock("@/components/viewers/ImageViewer", () => ({
  ImageViewer: ({
    blobUrl,
    filename,
  }: {
    blobUrl: string;
    filename: string;
    onDownload: () => void;
  }) => (
    <div
      data-testid="image-viewer"
      data-blob-url={blobUrl}
      data-filename={filename}
    />
  ),
}));

// Mock Dialog components to render inline
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({
    open,
    onOpenChange,
    children,
  }: {
    open: boolean;
    onOpenChange?: (open: boolean) => void;
    children: React.ReactNode;
  }) =>
    open ? (
      <div
        data-testid="dialog-root"
        data-on-open-change={String(!!onOpenChange)}
      >
        {children}
      </div>
    ) : null,
  DialogContent: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="dialog-content" className={className}>
      {children}
    </div>
  ),
  DialogHeader: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="dialog-header" className={className}>
      {children}
    </div>
  ),
  DialogTitle: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <h2 data-testid="dialog-title" className={className}>
      {children}
    </h2>
  ),
  DialogDescription: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <p data-testid="dialog-description" className={className}>
      {children}
    </p>
  ),
}));

// Mock Badge
vi.mock("@/components/ui/badge", () => ({
  Badge: ({
    children,
    variant,
    className,
  }: {
    children: React.ReactNode;
    variant?: string;
    className?: string;
  }) => (
    <span data-testid="badge" data-variant={variant} className={className}>
      {children}
    </span>
  ),
}));

// Mock Button - render plain button with text content
vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    variant,
    size,
    className,
    disabled,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    variant?: string;
    size?: string;
    className?: string;
    disabled?: boolean;
  }) => (
    <button
      onClick={onClick}
      data-variant={variant}
      data-size={size}
      className={className}
      disabled={disabled}
    >
      {children}
    </button>
  ),
}));

// Mock lucide-react icons so Button text is clean
vi.mock("lucide-react", () => ({
  Download: () => <span data-testid="icon-download" />,
  Minus: () => <span data-testid="icon-minus" />,
  Plus: () => <span data-testid="icon-plus" />,
  X: () => <span data-testid="icon-x" />,
}));

import { DocumentViewerModal } from "./DocumentViewerModal";
import { useDocumentFetch } from "@/hooks/useDocumentFetch";

const mockUseDocumentFetch = vi.mocked(useDocumentFetch);

const baseFile = {
  name: "readme.txt",
  type: "text/plain",
  size: 2048,
  subfolder: "attachments",
};

const defaultFetchResult = {
  content: "Hello, world!",
  blobUrl: null,
  loading: false,
  error: null,
};

describe("DocumentViewerModal", () => {
  beforeEach(() => {
    mockUseDocumentFetch.mockReturnValue(defaultFetchResult);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  // ---- AC #1: Modal opens from Files tab, shows header info ----

  it("renders modal when file prop is non-null", () => {
    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );
    expect(screen.getByTestId("dialog-root")).toBeInTheDocument();
  });

  it("does not render modal when file is null", () => {
    render(
      <DocumentViewerModal taskId="task_1" file={null} onClose={vi.fn()} />
    );
    expect(screen.queryByTestId("dialog-root")).toBeNull();
  });

  it("shows file name in modal header", () => {
    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );
    expect(screen.getByTestId("dialog-title")).toHaveTextContent("readme.txt");
  });

  it("shows file extension as type badge in header", () => {
    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );
    expect(screen.getByTestId("badge")).toHaveTextContent("TXT");
  });

  it("renders a dialog description for accessibility", () => {
    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );
    expect(screen.getByTestId("dialog-description")).toHaveTextContent(
      "Preview and download readme.txt"
    );
  });

  it("shows formatted file size in header", () => {
    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );
    // 2048 bytes = 2 KB
    expect(screen.getByText("2 KB")).toBeInTheDocument();
  });

  it("shows a Download button in modal header", () => {
    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );
    // Find button containing the download icon
    const downloadIcon = screen.getByTestId("icon-download");
    expect(downloadIcon.closest("button")).toBeInTheDocument();
  });

  it("shows a close (X) button in modal header", () => {
    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );
    const xIcon = screen.getByTestId("icon-x");
    expect(xIcon.closest("button")).toBeInTheDocument();
  });

  it("calls onClose when X button is clicked", () => {
    const onClose = vi.fn();
    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={onClose} />
    );
    const xIcon = screen.getByTestId("icon-x");
    fireEvent.click(xIcon.closest("button")!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Download button triggers anchor click with correct href and download attribute", () => {
    // Capture original before spying to avoid recursion
    const originalCreateElement = document.createElement.bind(document);
    const mockAnchor = { href: "", download: "", click: vi.fn() };
    const spy = vi
      .spyOn(document, "createElement")
      .mockImplementation((tag: string) => {
        if (tag === "a") return mockAnchor as unknown as HTMLElement;
        return originalCreateElement(tag);
      });

    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );

    // Click the download icon button in the header
    const downloadIcon = screen.getByTestId("icon-download");
    fireEvent.click(downloadIcon.closest("button")!);

    expect(mockAnchor.href).toBe(
      "/api/tasks/task_1/files/attachments/readme.txt"
    );
    expect(mockAnchor.download).toBe("readme.txt");
    expect(mockAnchor.click).toHaveBeenCalledTimes(1);

    spy.mockRestore();
  });

  // ---- AC #2: Text viewer with monospace font and zoom controls ----

  it("renders text file content in monospace pre element", () => {
    mockUseDocumentFetch.mockReturnValue({
      ...defaultFetchResult,
      content: "line1\nline2",
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "data.txt" }}
        onClose={vi.fn()}
      />
    );

    const pre = document.querySelector("pre");
    expect(pre).not.toBeNull();
    expect(pre?.className).toContain("font-mono");
    expect(pre?.textContent).toContain("line1");
  });

  it("renders text viewer with initial font size of 14px displayed", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "log.txt" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText("14px")).toBeInTheDocument();
  });

  it("zoom Plus button increments font size by 2", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "log.txt" }}
        onClose={vi.fn()}
      />
    );

    const plusIcons = screen.getAllByTestId("icon-plus");
    fireEvent.click(plusIcons[0].closest("button")!);
    expect(screen.getByText("16px")).toBeInTheDocument();
  });

  it("zoom Minus button decrements font size by 2", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "log.txt" }}
        onClose={vi.fn()}
      />
    );

    const minusIcons = screen.getAllByTestId("icon-minus");
    fireEvent.click(minusIcons[0].closest("button")!);
    expect(screen.getByText("12px")).toBeInTheDocument();
  });

  it("zoom is clamped to minimum of 10px", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "log.txt" }}
        onClose={vi.fn()}
      />
    );

    const minusIcons = screen.getAllByTestId("icon-minus");
    const minusBtn = minusIcons[0].closest("button")!;

    // Initial 14px, click Minus many times — min is 10
    for (let i = 0; i < 10; i++) {
      fireEvent.click(minusBtn);
    }
    expect(screen.getByText("10px")).toBeInTheDocument();
  });

  it("zoom is clamped to maximum of 24px", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "log.txt" }}
        onClose={vi.fn()}
      />
    );

    const plusIcons = screen.getAllByTestId("icon-plus");
    const plusBtn = plusIcons[0].closest("button")!;

    // Initial 14px, click Plus many times — max is 24
    for (let i = 0; i < 10; i++) {
      fireEvent.click(plusBtn);
    }
    expect(screen.getByText("24px")).toBeInTheDocument();
  });

  it("renders .json as text viewer (pre with font-mono)", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "config.json" }}
        onClose={vi.fn()}
      />
    );
    const pre = document.querySelector("pre");
    expect(pre).not.toBeNull();
    expect(screen.queryByTestId("syntax-highlighter")).toBeNull();
  });

  it("renders .csv as text viewer", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "data.csv" }}
        onClose={vi.fn()}
      />
    );
    expect(document.querySelector("pre")).not.toBeNull();
  });

  it("passes task markdown source context into MarkdownViewer", () => {
    mockUseDocumentFetch.mockReturnValue({
      ...defaultFetchResult,
      content: "![Chart](./chart.png)",
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "reports/summary.md", subfolder: "output" }}
        onClose={vi.fn()}
      />
    );

    const viewer = screen.getByTestId("markdown-viewer");
    expect(viewer).toHaveAttribute("data-task-id", "task_1");
    expect(viewer).toHaveAttribute("data-source-name", "reports/summary.md");
    expect(viewer).toHaveAttribute("data-source-subfolder", "output");
  });

  it("renders .yaml as text viewer", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "config.yaml" }}
        onClose={vi.fn()}
      />
    );
    expect(document.querySelector("pre")).not.toBeNull();
  });

  // ---- AC #3: Code viewer with syntax highlighting ----

  it("renders code file with SyntaxHighlighter", () => {
    mockUseDocumentFetch.mockReturnValue({
      ...defaultFetchResult,
      content: "def hello(): pass",
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "script.py" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("syntax-highlighter")).toBeInTheDocument();
  });

  it("passes correct language for .py -> python", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "script.py" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("syntax-highlighter")).toHaveAttribute(
      "data-language",
      "python"
    );
  });

  it("passes correct language for .ts -> typescript", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "utils.ts" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("syntax-highlighter")).toHaveAttribute(
      "data-language",
      "typescript"
    );
  });

  it("passes correct language for .js -> javascript", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "app.js" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("syntax-highlighter")).toHaveAttribute(
      "data-language",
      "javascript"
    );
  });

  it("passes correct language for .tsx -> tsx", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "Component.tsx" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("syntax-highlighter")).toHaveAttribute(
      "data-language",
      "tsx"
    );
  });

  it("passes showLineNumbers=true to SyntaxHighlighter", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "script.py" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("syntax-highlighter")).toHaveAttribute(
      "data-show-line-numbers",
      "true"
    );
  });

  it("renders code viewer with zoom controls showing initial font size", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "script.py" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText("14px")).toBeInTheDocument();
  });

  // ---- AC #4: Unsupported file type fallback ----

  it("shows 'Preview not available' for unsupported file type", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "archive.zip" }}
        onClose={vi.fn()}
      />
    );

    expect(
      screen.getByText("Preview not available for this file type.")
    ).toBeInTheDocument();
  });

  it("shows Download button in unsupported fallback body", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "archive.zip" }}
        onClose={vi.fn()}
      />
    );

    // Unsupported view renders a Download button in the body in addition to the header one
    const downloadIcons = screen.getAllByTestId("icon-download");
    expect(downloadIcons.length).toBeGreaterThanOrEqual(2);
  });

  it("does not render SyntaxHighlighter for unsupported types", () => {
    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "archive.zip" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.queryByTestId("syntax-highlighter")).toBeNull();
  });

  // ---- Loading and error states ----

  it("shows Loading indicator while content is being fetched", () => {
    mockUseDocumentFetch.mockReturnValue({
      content: null,
      blobUrl: null,
      loading: true,
      error: null,
    });

    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows error message on fetch failure", () => {
    mockUseDocumentFetch.mockReturnValue({
      content: null,
      blobUrl: null,
      loading: false,
      error: "HTTP 404",
    });

    render(
      <DocumentViewerModal taskId="task_1" file={baseFile} onClose={vi.fn()} />
    );

    expect(screen.getByText(/Error: HTTP 404/)).toBeInTheDocument();
  });

  // ---- Viewer routing (getViewerType via rendered output) ----

  it("renders pdf viewer stub for .pdf files", () => {
    mockUseDocumentFetch.mockReturnValue({
      content: null,
      blobUrl: "blob:http://localhost/some-id",
      loading: false,
      error: null,
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "report.pdf" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("pdf-viewer-stub")).toBeInTheDocument();
  });

  it("renders markdown viewer for .md files", () => {
    mockUseDocumentFetch.mockReturnValue({
      ...defaultFetchResult,
      content: "# Heading",
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "README.md" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("markdown-viewer")).toBeInTheDocument();
  });

  it("renders html viewer for .html files", () => {
    mockUseDocumentFetch.mockReturnValue({
      ...defaultFetchResult,
      content: "<h1>Hi</h1>",
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "page.html" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("html-viewer")).toBeInTheDocument();
  });

  it("renders image viewer for .png files", () => {
    mockUseDocumentFetch.mockReturnValue({
      content: null,
      blobUrl: "blob:http://localhost/img-id",
      loading: false,
      error: null,
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "photo.png" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("image-viewer")).toBeInTheDocument();
  });

  // ---- Extension edge cases: SVG, .htm, .yml ----

  it("routes .svg to image viewer (not code viewer)", () => {
    mockUseDocumentFetch.mockReturnValue({
      content: null,
      blobUrl: "blob:http://localhost/svg-id",
      loading: false,
      error: null,
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "icon.svg" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("image-viewer")).toBeInTheDocument();
    expect(screen.queryByTestId("syntax-highlighter")).toBeNull();
  });

  it("renders .htm as html viewer", () => {
    mockUseDocumentFetch.mockReturnValue({
      ...defaultFetchResult,
      content: "<p>hello</p>",
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "page.htm" }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("html-viewer")).toBeInTheDocument();
  });

  it("renders .yml as text viewer (pre with font-mono)", () => {
    mockUseDocumentFetch.mockReturnValue({
      ...defaultFetchResult,
      content: "key: value",
    });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "config.yml" }}
        onClose={vi.fn()}
      />
    );

    const pre = document.querySelector("pre");
    expect(pre).not.toBeNull();
    expect(pre?.className).toContain("font-mono");
    expect(screen.queryByTestId("syntax-highlighter")).toBeNull();
  });

  // ---- Download: verify encodeURIComponent is applied for special-char filenames ----

  it("Download button URL-encodes filename with special characters", () => {
    const originalCreateElement = document.createElement.bind(document);
    const mockAnchor = { href: "", download: "", click: vi.fn() };
    const spy = vi
      .spyOn(document, "createElement")
      .mockImplementation((tag: string) => {
        if (tag === "a") return mockAnchor as unknown as HTMLElement;
        return originalCreateElement(tag);
      });

    render(
      <DocumentViewerModal
        taskId="task_1"
        file={{ ...baseFile, name: "my report (2).txt" }}
        onClose={vi.fn()}
      />
    );

    const downloadIcon = screen.getByTestId("icon-download");
    fireEvent.click(downloadIcon.closest("button")!);

    expect(mockAnchor.href).toBe(
      "/api/tasks/task_1/files/attachments/my%20report%20(2).txt"
    );
    expect(mockAnchor.download).toBe("my report (2).txt");
    expect(mockAnchor.click).toHaveBeenCalledTimes(1);

    spy.mockRestore();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StepFileAttachment } from "./StepFileAttachment";

// Mock convex/react
const addTaskFilesMock = vi.fn().mockResolvedValue(undefined);
vi.mock("convex/react", () => ({
  useMutation: () => addTaskFilesMock,
}));

// Mock convex API
vi.mock("../convex/_generated/api", () => ({
  api: {
    tasks: {
      addTaskFiles: "tasks:addTaskFiles",
    },
  },
}));

vi.mock("./FileChip", () => ({
  FileChip: ({ name, onRemove }: { name: string; onRemove?: () => void }) => {
    const ext = name.split(".").pop()?.toLowerCase();
    const icon =
      ext === "pdf"
        ? "icon-pdf"
        : ["png", "jpg", "jpeg", "gif", "svg", "webp"].includes(ext ?? "")
          ? "icon-image"
          : ["py", "ts", "tsx", "js", "jsx", "go", "rs", "java", "sh"].includes(ext ?? "")
            ? "icon-code"
            : "icon-generic";

    return (
      <div>
        <span data-testid={icon} />
        <span title={name}>{name}</span>
        {onRemove ? (
          <button aria-label={`Remove ${name}`} onClick={onRemove}>
            remove
          </button>
        ) : null}
      </div>
    );
  },
}));

// Mock fetch for file upload
const fetchMock = vi.fn();
global.fetch = fetchMock;

const defaultProps = {
  stepTempId: "step_1",
  attachedFiles: [],
  taskId: "task-abc",
  onFilesAttached: vi.fn(),
  onFileRemoved: vi.fn(),
};

describe("StepFileAttachment", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders Attach button when no files are attached (empty state)", () => {
    render(<StepFileAttachment {...defaultProps} />);
    expect(screen.getByRole("button", { name: /attach/i })).toBeInTheDocument();
    // No file list should be shown
    expect(screen.queryByRole("button", { name: /remove/i })).toBeNull();
  });

  it("does not show file list when attachedFiles is empty", () => {
    render(<StepFileAttachment {...defaultProps} attachedFiles={[]} />);
    // No file names visible
    const xButtons = screen.queryAllByLabelText(/^Remove /);
    expect(xButtons).toHaveLength(0);
  });

  it("renders file list when files are attached", () => {
    render(<StepFileAttachment {...defaultProps} attachedFiles={["report.pdf", "data.csv"]} />);
    expect(screen.getByTitle("report.pdf")).toBeInTheDocument();
    expect(screen.getByTitle("data.csv")).toBeInTheDocument();
  });

  it("still renders Attach button when files are attached", () => {
    render(<StepFileAttachment {...defaultProps} attachedFiles={["report.pdf"]} />);
    expect(screen.getByRole("button", { name: /attach/i })).toBeInTheDocument();
  });

  it("shows FileText icon for PDF files", () => {
    render(<StepFileAttachment {...defaultProps} attachedFiles={["document.pdf"]} />);
    expect(screen.getByTitle("document.pdf")).toBeInTheDocument();
    expect(screen.getByTestId("icon-pdf")).toBeInTheDocument();
  });

  it("shows Image icon for image files", () => {
    render(<StepFileAttachment {...defaultProps} attachedFiles={["photo.png"]} />);
    expect(screen.getByTitle("photo.png")).toBeInTheDocument();
    expect(screen.getByTestId("icon-image")).toBeInTheDocument();
  });

  it("shows FileCode icon for code files", () => {
    render(<StepFileAttachment {...defaultProps} attachedFiles={["script.py"]} />);
    expect(screen.getByTitle("script.py")).toBeInTheDocument();
    expect(screen.getByTestId("icon-code")).toBeInTheDocument();
  });

  it("shows File icon for other file types", () => {
    render(<StepFileAttachment {...defaultProps} attachedFiles={["data.xyz"]} />);
    expect(screen.getByTitle("data.xyz")).toBeInTheDocument();
    expect(screen.getByTestId("icon-generic")).toBeInTheDocument();
  });

  it("calls onFileRemoved when X button is clicked on an attached file", () => {
    const onFileRemoved = vi.fn();
    render(
      <StepFileAttachment
        {...defaultProps}
        attachedFiles={["report.pdf"]}
        onFileRemoved={onFileRemoved}
      />,
    );

    const removeButton = screen.getByLabelText("Remove report.pdf");
    fireEvent.click(removeButton);

    expect(onFileRemoved).toHaveBeenCalledWith("step_1", "report.pdf");
  });

  it("shows loading spinner on Attach button during upload", async () => {
    // Simulate a slow fetch
    let resolveFetch: (value: unknown) => void;
    fetchMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );

    render(<StepFileAttachment {...defaultProps} />);

    const fileInput = screen
      .getByLabelText("Attach files to step")
      .closest("input") as HTMLInputElement;

    const file = new File(["content"], "test.txt", { type: "text/plain" });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    // While uploading, the button should be disabled
    await waitFor(() => {
      const button = screen.getByRole("button", { name: /attach/i });
      expect(button).toBeDisabled();
    });

    // Resolve the fetch inside act() to avoid React state update warnings
    await act(async () => {
      resolveFetch!({
        ok: true,
        json: async () => ({ files: [] }),
      });
    });
  });

  it("shows upload error text when upload fails", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500 });

    render(<StepFileAttachment {...defaultProps} />);

    const fileInput = screen
      .getByLabelText("Attach files to step")
      .closest("input") as HTMLInputElement;

    const file = new File(["content"], "test.txt", { type: "text/plain" });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(screen.getByText("Upload failed")).toBeInTheDocument();
    });
  });

  it("calls onFilesAttached with new file names on successful upload", async () => {
    const onFilesAttached = vi.fn();
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        files: [
          {
            name: "report.pdf",
            type: "application/pdf",
            size: 1024,
            subfolder: "attachments",
            uploadedAt: "2026-01-01",
          },
        ],
      }),
    });

    render(<StepFileAttachment {...defaultProps} onFilesAttached={onFilesAttached} />);

    const fileInput = screen
      .getByLabelText("Attach files to step")
      .closest("input") as HTMLInputElement;

    const file = new File(["content"], "report.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(onFilesAttached).toHaveBeenCalledWith("step_1", ["report.pdf"]);
    });
  });

  it("deduplicates file names when already attached", async () => {
    const onFilesAttached = vi.fn();
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        files: [
          {
            name: "report.pdf",
            type: "application/pdf",
            size: 1024,
            subfolder: "attachments",
            uploadedAt: "2026-01-01",
          },
        ],
      }),
    });

    render(
      <StepFileAttachment
        {...defaultProps}
        attachedFiles={["report.pdf"]} // already attached
        onFilesAttached={onFilesAttached}
      />,
    );

    const fileInput = screen
      .getByLabelText("Attach files to step")
      .closest("input") as HTMLInputElement;

    const file = new File(["content"], "report.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      // onFilesAttached should NOT be called since the file is already attached
      expect(onFilesAttached).not.toHaveBeenCalled();
    });
  });
});

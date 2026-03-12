import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { TaskInput } from "@/features/tasks/components/TaskInput";
import type { TaskInputData } from "@/features/tasks/hooks/useTaskInputData";

// Mock the feature hook instead of convex/react
const mockCreateTask = vi.fn();
const mockUpsertAttrValue = vi.fn();

const defaultHookData: TaskInputData = {
  createTask: mockCreateTask,
  predefinedTags: [],
  allAttributes: [],
  upsertAttrValue: mockUpsertAttrValue,
  isAutoTitle: false,
};

let hookOverrides: Partial<TaskInputData> = {};

vi.mock("@/features/tasks/hooks/useTaskInputData", () => ({
  useTaskInputData: () => ({ ...defaultHookData, ...hookOverrides }),
}));

vi.mock("@/components/ui/select", async () => import("../tests/mocks/select-mock"));

const mockAgents = [
  {
    name: "coder",
    displayName: "Coder Agent",
    role: "developer",
    skills: [],
    status: "idle" as const,
    enabled: true,
  },
  {
    name: "reviewer",
    displayName: "Reviewer Agent",
    role: "reviewer",
    skills: [],
    status: "idle" as const,
    enabled: true,
  },
  {
    name: "disabled-bot",
    displayName: "Disabled Bot",
    role: "tester",
    skills: [],
    status: "idle" as const,
    enabled: false,
  },
];

vi.mock("@/hooks/useSelectableAgents", () => ({
  useSelectableAgents: () => mockAgents,
}));

vi.mock("@/components/BoardContext", () => ({
  useBoard: () => ({
    activeBoardId: undefined,
  }),
}));

function setFileInputFiles(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, "files", {
    configurable: true,
    value: files,
  });
}

function getFileInput(): HTMLInputElement {
  const input = document.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) {
    throw new Error("TaskInput file input not found");
  }
  return input;
}

describe("TaskInput", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    hookOverrides = {};
    mockCreateTask.mockResolvedValue("task-123");
    mockUpsertAttrValue.mockResolvedValue(undefined);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
      })
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders the current title-first layout", () => {
    render(<TaskInput />);

    expect(screen.getByPlaceholderText("Task title...")).toBeInTheDocument();
    expect(screen.getByText("Create")).toBeInTheDocument();
    expect(screen.getByLabelText("Attach files")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Switch to manual mode/i })).toBeInTheDocument();
  });

  it("shows title validation errors and clears them when typing", () => {
    render(<TaskInput />);

    fireEvent.click(screen.getByText("Create"));
    expect(screen.getByText("Task title required")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Investigate issue" },
    });

    expect(screen.queryByText("Task title required")).not.toBeInTheDocument();
  });

  it("submits with autonomous supervision by default", async () => {
    render(<TaskInput />);

    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Research AI trends" },
    });
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(mockCreateTask).toHaveBeenCalledWith({
        title: "Research AI trends",
        description: undefined,
        tags: undefined,
        boardId: undefined,
        supervisionMode: "autonomous",
      });
    });
  });

  it("submits with supervised mode after toggling supervision", async () => {
    render(<TaskInput />);

    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Needs review first" },
    });
    fireEvent.click(screen.getByTitle("Autonomous"));
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(mockCreateTask).toHaveBeenCalledWith({
        title: "Needs review first",
        description: undefined,
        tags: undefined,
        boardId: undefined,
        supervisionMode: "supervised",
      });
    });
  });

  it("allows selecting a specific enabled agent", async () => {
    render(<TaskInput />);

    fireEvent.click(screen.getByRole("option", { name: "Reviewer Agent" }));
    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Escalate to reviewer" },
    });
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(mockCreateTask).toHaveBeenCalledWith({
        title: "Escalate to reviewer",
        description: undefined,
        tags: undefined,
        boardId: undefined,
        supervisionMode: "autonomous",
        assignedAgent: "reviewer",
      });
    });
  });

  it("renders disabled agents as deactivated options without selecting them by default", () => {
    render(<TaskInput />);

    const disabledOption = screen.getByRole("option", { name: "Disabled Bot (Deactivated)" });
    expect(disabledOption).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("combobox")).toHaveAttribute(
      "data-selected-value",
      "auto"
    );
  });

  it("switches to manual mode and submits a manual task", async () => {
    render(<TaskInput />);

    fireEvent.click(screen.getByRole("button", { name: /Switch to manual mode/i }));
    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Write release notes manually" },
    });
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(mockCreateTask).toHaveBeenCalledWith({
        title: "Write release notes manually",
        description: undefined,
        tags: undefined,
        boardId: undefined,
        isManual: true,
        supervisionMode: "autonomous",
      });
    });

    expect(screen.queryByText("Auto (Lead Agent)")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Switch to AI mode/i })).toBeInTheDocument();
  });

  it("shows pending file chips with formatted sizes and allows removing them", async () => {
    render(<TaskInput />);

    const fileInput = getFileInput();
    const pdf = new File([new Uint8Array(1024)], "report.pdf", {
      type: "application/pdf",
    });
    const archive = new File([new Uint8Array(2_621_440)], "bundle.zip", {
      type: "application/zip",
    });
    setFileInputFiles(fileInput, [pdf, archive]);
    fireEvent.change(fileInput);

    expect(screen.getByText("report.pdf (1 KB)")).toBeInTheDocument();
    expect(screen.getByText("bundle.zip (2.5 MB)")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Remove report.pdf"));
    expect(screen.queryByText("report.pdf (1 KB)")).not.toBeInTheDocument();
    expect(screen.getByText("bundle.zip (2.5 MB)")).toBeInTheDocument();
  });

  it("includes file metadata in task creation and uploads files after create", async () => {
    const fetchMock = vi.mocked(fetch);
    render(<TaskInput />);

    const fileInput = getFileInput();
    const pdf = new File([new Uint8Array(2048)], "report.pdf", {
      type: "application/pdf",
    });
    setFileInputFiles(fileInput, [pdf]);
    fireEvent.change(fileInput);

    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Create task with files" },
    });
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(mockCreateTask).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Create task with files",
          supervisionMode: "autonomous",
          files: [
            expect.objectContaining({
              name: "report.pdf",
              type: "application/pdf",
              size: 2048,
              subfolder: "attachments",
            }),
          ],
        })
      );
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tasks/task-123/files",
        expect.objectContaining({
          method: "POST",
          body: expect.any(FormData),
        })
      );
    });
  });

  it("clears pending files after a successful upload", async () => {
    render(<TaskInput />);

    const fileInput = getFileInput();
    const pdf = new File([new Uint8Array(1024)], "report.pdf", {
      type: "application/pdf",
    });
    setFileInputFiles(fileInput, [pdf]);
    fireEvent.change(fileInput);

    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Upload attachments" },
    });
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(screen.queryByText("report.pdf (1 KB)")).not.toBeInTheDocument();
    });
  });

  it("shows an upload error and keeps pending files when disk upload fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
      })
    );
    render(<TaskInput />);

    const fileInput = getFileInput();
    const pdf = new File([new Uint8Array(1024)], "report.pdf", {
      type: "application/pdf",
    });
    setFileInputFiles(fileInput, [pdf]);
    fireEvent.change(fileInput);

    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Broken upload" },
    });
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(
        screen.getByText("Task created, but file upload to disk failed. Please retry.")
      ).toBeInTheDocument();
    });
    expect(screen.getByText("report.pdf (1 KB)")).toBeInTheDocument();
  });

  it("submits with Enter from the title field", async () => {
    render(<TaskInput />);

    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Keyboard submit" },
    });
    fireEvent.keyDown(screen.getByPlaceholderText("Task title..."), {
      key: "Enter",
    });

    await waitFor(() => {
      expect(mockCreateTask).toHaveBeenCalledWith({
        title: "Keyboard submit",
        description: undefined,
        tags: undefined,
        boardId: undefined,
        supervisionMode: "autonomous",
      });
    });
  });

  it("resets the title and supervision toggle after a successful submission", async () => {
    render(<TaskInput />);

    fireEvent.change(screen.getByPlaceholderText("Task title..."), {
      target: { value: "Reset me" },
    });
    fireEvent.click(screen.getByTitle("Autonomous"));
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Task title...")
      ).toHaveValue("");
    });
    expect(screen.getByTitle("Autonomous")).toBeInTheDocument();
  });
});

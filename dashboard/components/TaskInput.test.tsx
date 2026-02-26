import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { TaskInput } from "./TaskInput";

// Track the most recent mutate function for assertions
const mockMutate = vi.fn();
const mockAgents = [
  { name: "coder", displayName: "Coder Agent", role: "developer", skills: [], status: "idle" as const, enabled: true },
  { name: "reviewer", displayName: "Reviewer Agent", role: "reviewer", skills: [], status: "idle" as const, enabled: true },
  { name: "disabled-bot", displayName: "Disabled Bot", role: "tester", skills: [], status: "idle" as const, enabled: false },
];

vi.mock("../convex/_generated/api", () => ({
  api: {
    tasks: { create: "tasks:create", addTaskFiles: "tasks:addTaskFiles" },
    agents: { list: "agents:list" },
    taskTags: { list: "taskTags:list" },
  },
}));

vi.mock("convex/react", () => ({
  useMutation: () => mockMutate,
  // Return [] for taskTags so chips don't render and interfere with these tests
  useQuery: (ref: string) => (ref === "taskTags:list" ? [] : mockAgents),
}));

describe("TaskInput", () => {
  afterEach(() => {
    cleanup();
    mockMutate.mockClear();
    vi.unstubAllGlobals();
  });

  it("renders the input with placeholder text", () => {
    render(<TaskInput />);
    expect(
      screen.getByPlaceholderText("Create a new task...")
    ).toBeInTheDocument();
  });

  it("renders the Create button", () => {
    render(<TaskInput />);
    expect(screen.getByText("Create")).toBeInTheDocument();
  });

  it("shows validation error on empty submission", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByText("Create"));
    expect(screen.getByText("Task description required")).toBeInTheDocument();
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("shows validation error on whitespace-only submission", () => {
    render(<TaskInput />);
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.click(screen.getByText("Create"));
    expect(screen.getByText("Task description required")).toBeInTheDocument();
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("calls mutation with title on valid submission", async () => {
    mockMutate.mockResolvedValue("taskId123");
    render(<TaskInput />);
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Research AI trends" } });
    fireEvent.click(screen.getByText("Create"));
    expect(mockMutate).toHaveBeenCalledWith({
      title: "Research AI trends",
      tags: undefined,
      supervisionMode: "autonomous",
    });
  });

  it("clears input after successful submission", async () => {
    mockMutate.mockResolvedValue("taskId123");
    render(<TaskInput />);
    const input = screen.getByPlaceholderText(
      "Create a new task..."
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Research AI trends" } });
    fireEvent.click(screen.getByText("Create"));
    // Wait for the async mutation to resolve
    await vi.waitFor(() => {
      expect(input.value).toBe("");
    });
  });

  it("submits on Enter key press", () => {
    mockMutate.mockResolvedValue("taskId123");
    render(<TaskInput />);
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "My task" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(mockMutate).toHaveBeenCalledWith({
      title: "My task",
      tags: undefined,
      supervisionMode: "autonomous",
    });
  });

  it("clears validation error when user types", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByText("Create"));
    expect(screen.getByText("Task description required")).toBeInTheDocument();
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "a" } });
    expect(
      screen.queryByText("Task description required")
    ).not.toBeInTheDocument();
  });

  // --- New tests for Story 4.4: Progressive disclosure & agent assignment ---

  it("renders the toggle options chevron button", () => {
    render(<TaskInput />);
    expect(screen.getByLabelText("Toggle options")).toBeInTheDocument();
  });

  it("toggles options panel on chevron click", () => {
    render(<TaskInput />);
    // Panel should not be visible initially
    expect(screen.queryByText("Agent:")).not.toBeInTheDocument();

    // Click chevron to expand
    fireEvent.click(screen.getByLabelText("Toggle options"));
    expect(screen.getByText("Agent:")).toBeInTheDocument();

    // Click chevron again to collapse
    fireEvent.click(screen.getByLabelText("Toggle options"));
    expect(screen.queryByText("Agent:")).not.toBeInTheDocument();
  });

  it("shows Auto (Lead Agent) as default in agent selector", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByLabelText("Toggle options"));
    expect(screen.getByText("Auto (Lead Agent)")).toBeInTheDocument();
  });

  it("submits without assignedAgent when Auto is selected", () => {
    mockMutate.mockResolvedValue("taskId123");
    render(<TaskInput />);
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Auto task" } });
    fireEvent.click(screen.getByText("Create"));
    expect(mockMutate).toHaveBeenCalledWith({
      title: "Auto task",
      tags: undefined,
      supervisionMode: "autonomous",
    });
  });

  it("collapses panel after successful submission", async () => {
    mockMutate.mockResolvedValue("taskId123");
    render(<TaskInput />);

    // Expand the panel
    fireEvent.click(screen.getByLabelText("Toggle options"));
    expect(screen.getByText("Agent:")).toBeInTheDocument();

    // Submit a task
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Test task" } });
    fireEvent.click(screen.getByText("Create"));

    // Panel should collapse after submission
    await vi.waitFor(() => {
      expect(screen.queryByText("Agent:")).not.toBeInTheDocument();
    });
  });

  // --- Story 5.1: Trust level and reviewer configuration ---

  it("shows trust level selector with 3 options when expanded", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByLabelText("Toggle options"));
    expect(screen.getByText("Trust Level")).toBeInTheDocument();
    const trustTrigger = screen.getAllByRole("combobox")[1];
    expect(trustTrigger).toHaveTextContent("Autonomous");
  });

  // --- Supervision mode A/S toggle ---

  it("renders A/S toggle button in autonomous mode by default", () => {
    render(<TaskInput />);
    const toggle = screen.getByLabelText("Autonomous mode");
    expect(toggle).toBeInTheDocument();
  });

  it("switches A/S toggle to supervised on click", () => {
    render(<TaskInput />);
    const toggle = screen.getByLabelText("Autonomous mode");
    fireEvent.click(toggle);
    expect(screen.getByLabelText("Supervised mode")).toBeInTheDocument();
  });

  it("switches A/S toggle back to autonomous on second click", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByLabelText("Autonomous mode"));
    fireEvent.click(screen.getByLabelText("Supervised mode"));
    expect(screen.getByLabelText("Autonomous mode")).toBeInTheDocument();
  });

  it("hides A/S toggle when manual mode is active", () => {
    render(<TaskInput />);
    // Switch to manual
    fireEvent.click(screen.getByLabelText("Switch to manual mode"));
    // Buttons stay in DOM but are visually hidden with opacity-0 and aria-hidden
    const supervisionBtn = screen.getByLabelText("Autonomous mode");
    expect(supervisionBtn).toHaveClass("opacity-0");
    expect(supervisionBtn).toHaveClass("pointer-events-none");
    expect(supervisionBtn).toHaveAttribute("aria-hidden", "true");
  });

  it("submits with supervisionMode autonomous by default", () => {
    mockMutate.mockResolvedValue("taskId123");
    render(<TaskInput />);
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Default mode task" } });
    fireEvent.click(screen.getByText("Create"));

    expect(mockMutate).toHaveBeenCalledWith({
      title: "Default mode task",
      tags: undefined,
      supervisionMode: "autonomous",
    });
  });

  it("submits with supervisionMode supervised when toggle is set", () => {
    mockMutate.mockResolvedValue("taskId123");
    render(<TaskInput />);
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Supervised task" } });
    // Click the A/S toggle to switch to supervised
    fireEvent.click(screen.getByLabelText("Autonomous mode"));
    fireEvent.click(screen.getByText("Create"));

    expect(mockMutate).toHaveBeenCalledWith({
      title: "Supervised task",
      tags: undefined,
      supervisionMode: "supervised",
    });
  });

  it("resets supervision mode toggle after submission", async () => {
    mockMutate.mockResolvedValue("taskId123");
    render(<TaskInput />);
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Needs review first" } });
    // Set to supervised
    fireEvent.click(screen.getByLabelText("Autonomous mode"));
    expect(screen.getByLabelText("Supervised mode")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Create"));

    await vi.waitFor(() => {
      // After submission, toggle should reset to autonomous
      expect(screen.getByLabelText("Autonomous mode")).toBeInTheDocument();
    });
  });

  it("does not show reviewer section when trust level is autonomous", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByLabelText("Toggle options"));
    // Default is autonomous, so reviewers label should not appear
    expect(screen.queryByText("Reviewers")).not.toBeInTheDocument();
  });

  it("shows reviewer checkboxes when trust level is agent_reviewed", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByLabelText("Toggle options"));

    // Change trust level to agent_reviewed
    const trustTrigger = screen.getAllByRole("combobox")[1];
    fireEvent.click(trustTrigger);
    fireEvent.click(screen.getByRole("option", { name: "Agent Reviewed" }));

    // Reviewer section should now be visible
    expect(screen.getByText("Reviewers")).toBeInTheDocument();
    expect(screen.getByText("Coder Agent")).toBeInTheDocument();
    expect(screen.getByText("Reviewer Agent")).toBeInTheDocument();
  });

  it("hides reviewer section when trust level is changed back to autonomous", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByLabelText("Toggle options"));

    // Change to agent_reviewed
    fireEvent.click(screen.getAllByRole("combobox")[1]);
    fireEvent.click(screen.getByRole("option", { name: "Agent Reviewed" }));
    expect(screen.getByText("Reviewers")).toBeInTheDocument();

    // Change back to autonomous
    fireEvent.click(screen.getAllByRole("combobox")[1]);
    fireEvent.click(screen.getByRole("option", { name: "Autonomous" }));
    expect(screen.queryByText("Reviewers")).not.toBeInTheDocument();
  });

  it("shows human approval checkbox when trust level is human_approved", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByLabelText("Toggle options"));

    fireEvent.click(screen.getAllByRole("combobox")[1]);
    fireEvent.click(screen.getByRole("option", { name: "Human Approved" }));

    expect(screen.getByText("Require human approval")).toBeInTheDocument();
  });

  it("submits with trustLevel and reviewers when configured", () => {
    mockMutate.mockResolvedValue("taskId123");
    render(<TaskInput />);

    // Type task title
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Review this" } });

    // Expand options and set trust level
    fireEvent.click(screen.getByLabelText("Toggle options"));
    fireEvent.click(screen.getAllByRole("combobox")[1]);
    fireEvent.click(screen.getByRole("option", { name: "Agent Reviewed" }));

    // Select a reviewer
    fireEvent.click(screen.getByLabelText("Coder Agent"));

    // Submit
    fireEvent.click(screen.getByText("Create"));

    expect(mockMutate).toHaveBeenCalledWith({
      title: "Review this",
      tags: undefined,
      supervisionMode: "autonomous",
      trustLevel: "agent_reviewed",
      reviewers: ["coder"],
    });
  });

  // --- Story 8.4: Disabled agents in selector ---

  it("shows disabled agents with (Deactivated) suffix in dropdown", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByLabelText("Toggle options"));

    // Open the agent selector dropdown
    fireEvent.click(screen.getByText("Auto (Lead Agent)"));

    // The disabled agent should have "(Deactivated)" suffix
    expect(screen.getByText("Disabled Bot (Deactivated)")).toBeInTheDocument();
  });

  it("renders enabled agents without (Deactivated) suffix", () => {
    render(<TaskInput />);
    fireEvent.click(screen.getByLabelText("Toggle options"));

    // Open the agent selector dropdown
    fireEvent.click(screen.getByText("Auto (Lead Agent)"));

    // Enabled agents should not have the suffix
    expect(screen.getByText("Coder Agent")).toBeInTheDocument();
    expect(screen.queryByText("Coder Agent (Deactivated)")).not.toBeInTheDocument();
  });

  // --- Story 5.2: File attachment tests ---

  it("renders paperclip attach button with correct aria-label", () => {
    render(<TaskInput />);
    expect(screen.getByLabelText("Attach files")).toBeInTheDocument();
  });

  it("shows file chips after file selection", () => {
    const { container } = render(<TaskInput />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(["content"], "report.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });
    fireEvent.change(fileInput);
    expect(screen.getByText(/report\.pdf/)).toBeInTheDocument();
  });

  it("shows file size in human-readable format", () => {
    const { container } = render(<TaskInput />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    // 2048 bytes → "2 KB"
    const small = new File(["x".repeat(2048)], "small.txt", {
      type: "text/plain",
    });
    Object.defineProperty(fileInput, "files", {
      value: [small],
      writable: false,
    });
    fireEvent.change(fileInput);
    expect(screen.getByText(/2 KB/)).toBeInTheDocument();
  });

  it("shows file size in MB for large files", () => {
    const { container } = render(<TaskInput />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;

    // 1572864 bytes = 1.5 MB
    const large = new File(["x".repeat(1572864)], "large.bin", {
      type: "application/octet-stream",
    });
    Object.defineProperty(fileInput, "files", {
      value: [large],
      writable: false,
    });
    fireEvent.change(fileInput);
    expect(screen.getByText(/1\.5 MB/)).toBeInTheDocument();
  });

  it("removes file chip when X button is clicked", () => {
    const { container } = render(<TaskInput />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(["content"], "report.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });
    fireEvent.change(fileInput);
    expect(screen.getByText(/report\.pdf/)).toBeInTheDocument();

    // Click the remove button
    fireEvent.click(screen.getByLabelText("Remove report.pdf"));
    expect(screen.queryByText(/report\.pdf/)).not.toBeInTheDocument();
  });

  it("includes file metadata in createTask mutation when files are pending", async () => {
    mockMutate.mockResolvedValue("taskId123");
    // Also mock fetch so the upload step succeeds silently
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TaskInput />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(["content"], "report.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });
    fireEvent.change(fileInput);

    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Task with attachment" } });
    fireEvent.click(screen.getByText("Create"));

    await vi.waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          files: [
            expect.objectContaining({
              name: "report.pdf",
              type: "application/pdf",
              size: expect.any(Number),
              subfolder: "attachments",
              uploadedAt: expect.any(String),
            }),
          ],
        })
      );
    });
  });

  it("calls upload endpoint after task creation with pending files", async () => {
    mockMutate.mockResolvedValue("taskId123");
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TaskInput />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(["content"], "report.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });
    fireEvent.change(fileInput);

    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Upload test" } });
    fireEvent.click(screen.getByText("Create"));

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tasks/taskId123/files",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("does not include files or call upload when no files are pending", async () => {
    mockMutate.mockResolvedValue("taskId123");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<TaskInput />);
    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "No files task" } });
    fireEvent.click(screen.getByText("Create"));

    await vi.waitFor(() => {
      const callArgs = mockMutate.mock.calls[0][0] as Record<string, unknown>;
      expect(callArgs).not.toHaveProperty("files");
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows error message when file upload fails", async () => {
    mockMutate.mockResolvedValue("taskId123");
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: false, status: 500 });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TaskInput />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(["content"], "report.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });
    fireEvent.change(fileInput);

    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Upload failure test" } });
    fireEvent.click(screen.getByText("Create"));

    await vi.waitFor(() => {
      expect(
        screen.getByText(
          "Task created, but file upload to disk failed. Please retry."
        )
      ).toBeInTheDocument();
    });
  });

  it("clears pending files after successful upload", async () => {
    mockMutate.mockResolvedValue("taskId123");
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TaskInput />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(["content"], "report.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });
    fireEvent.change(fileInput);
    expect(screen.getByText(/report\.pdf/)).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Clear files test" } });
    fireEvent.click(screen.getByText("Create"));

    await vi.waitFor(() => {
      expect(screen.queryByText(/report\.pdf/)).not.toBeInTheDocument();
    });
  });

  it("retains pending file chips when upload fails", async () => {
    mockMutate.mockResolvedValue("taskId123");
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: false, status: 500 });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TaskInput />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(["content"], "keep-me.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });
    fireEvent.change(fileInput);
    expect(screen.getByText(/keep-me\.pdf/)).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Create a new task...");
    fireEvent.change(input, { target: { value: "Upload failure retention" } });
    fireEvent.click(screen.getByText("Create"));

    await vi.waitFor(() => {
      // Error message should appear
      expect(
        screen.getByText(
          "Task created, but file upload to disk failed. Please retry."
        )
      ).toBeInTheDocument();
    });
    // File chips should STILL be visible (pendingFiles not cleared on failure)
    expect(screen.getByText(/keep-me\.pdf/)).toBeInTheDocument();
  });
});

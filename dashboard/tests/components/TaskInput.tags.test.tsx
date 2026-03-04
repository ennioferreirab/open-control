import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Use delay:null for all user interactions so keystrokes are dispatched
// synchronously via microtasks — avoids ~1s per character in jsdom.
const user = userEvent.setup({ delay: null });

vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    tasks: { create: "tasks:create" },
    agents: { list: "agents:list" },
    taskTags: { list: "taskTags:list" },
  },
}));

import { useQuery, useMutation } from "convex/react";
import { TaskInput } from "../../components/TaskInput";

const mockUseQuery = useQuery as ReturnType<typeof vi.fn>;
const mockUseMutation = useMutation as ReturnType<typeof vi.fn>;

const SAMPLE_TAGS = [
  { _id: "t1", name: "bug", color: "red" },
  { _id: "t2", name: "feature", color: "blue" },
];

describe("TaskInput — tag selection", () => {
  const mockCreateTask = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseMutation.mockReturnValue(mockCreateTask);
    mockCreateTask.mockResolvedValue(undefined);
    mockUseQuery.mockImplementation((ref) => {
      if (String(ref).includes("taskTags")) return SAMPLE_TAGS;
      return [];
    });
  });

  it("shows tag chips without expanding collapsible", () => {
    render(<TaskInput />);
    // Chips visible immediately — no expand needed
    expect(screen.getByRole("button", { name: "bug" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "feature" })).toBeInTheDocument();
  });

  it("shows no tag chips when no tags defined", () => {
    mockUseQuery.mockImplementation((ref) => {
      if (String(ref).includes("taskTags")) return [];
      return [];
    });
    render(<TaskInput />);
    expect(screen.queryByRole("button", { name: "bug" })).not.toBeInTheDocument();
  });

  it("passes selected tags to createTask when chip is clicked", async () => {
    render(<TaskInput />);
    const titleInput = screen.getByPlaceholderText("Create a new task...");
    await user.type(titleInput, "My task");

    await user.click(screen.getByRole("button", { name: "bug" }));
    await user.click(screen.getByRole("button", { name: /^Create$/ }));

    await waitFor(() => {
      expect(mockCreateTask).toHaveBeenCalledWith(
        expect.objectContaining({ tags: ["bug"] })
      );
    });
  });

  it("does NOT include tags in args when none are selected", async () => {
    render(<TaskInput />);
    const titleInput = screen.getByPlaceholderText("Create a new task...");
    await user.type(titleInput, "Clean task");
    await user.click(screen.getByRole("button", { name: /^Create$/ }));
    await waitFor(() => {
      const call = mockCreateTask.mock.calls[0][0];
      expect(call.tags).toBeUndefined();
    });
  });

  it("resets selectedTags to [] after successful task creation", async () => {
    render(<TaskInput />);
    const titleInput = screen.getByPlaceholderText("Create a new task...");
    await user.type(titleInput, "Task with tag");

    const bugChip = screen.getByRole("button", { name: "bug" });
    await user.click(bugChip);
    expect(bugChip).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: /^Create$/ }));
    await waitFor(() => expect(titleInput).toHaveValue(""));

    expect(screen.getByRole("button", { name: "bug" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("resets selectedTags when switching to manual mode (M1 regression guard)", async () => {
    render(<TaskInput />);

    // Select a tag
    const bugChip = screen.getByRole("button", { name: "bug" });
    await user.click(bugChip);
    expect(bugChip).toHaveAttribute("aria-pressed", "true");

    // Switch to manual mode (clears tags)
    await user.click(
      screen.getByRole("button", { name: /Switch to manual mode/i })
    );

    // Switch back to AI mode
    await user.click(
      screen.getByRole("button", { name: /Switch to AI mode/i })
    );

    // Chip should be deselected
    expect(screen.getByRole("button", { name: "bug" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });
});

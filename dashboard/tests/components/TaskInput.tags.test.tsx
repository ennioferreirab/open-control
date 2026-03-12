import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TaskInput } from "../../features/tasks/components/TaskInput";
import type { TaskInputData } from "@/features/tasks/hooks/useTaskInputData";

const SAMPLE_TAGS = [
  { _id: "t1", name: "bug", color: "red" },
  { _id: "t2", name: "feature", color: "blue" },
];

// Mock the feature hook instead of convex/react
const mockCreateTask = vi.fn();
const mockUpsertAttrValue = vi.fn();

let hookOverrides: Partial<TaskInputData> = {};

const defaultHookData: TaskInputData = {
  createTask: mockCreateTask,
  predefinedTags: SAMPLE_TAGS as never[],
  allAttributes: [],
  upsertAttrValue: mockUpsertAttrValue,
  isAutoTitle: false,
};

vi.mock("@/features/tasks/hooks/useTaskInputData", () => ({
  useTaskInputData: () => ({ ...defaultHookData, ...hookOverrides }),
}));

vi.mock("@/components/ui/select", async () => import("../mocks/select-mock"));

vi.mock("@/hooks/useSelectableAgents", () => ({
  useSelectableAgents: () => [],
}));

vi.mock("@/components/BoardContext", () => ({
  useBoard: () => ({
    activeBoardId: undefined,
  }),
}));

describe("TaskInput tag selection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    hookOverrides = {};
    mockCreateTask.mockResolvedValue("task-123");
    mockUpsertAttrValue.mockResolvedValue(undefined);
  });

  it("shows tag chips without extra expansion UI", () => {
    render(<TaskInput />);

    expect(screen.getByRole("button", { name: "bug" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "feature" })).toBeInTheDocument();
  });

  it("shows no tag chips when no tags are configured", () => {
    hookOverrides = { predefinedTags: [] };
    render(<TaskInput />);
    expect(screen.queryByRole("button", { name: "bug" })).not.toBeInTheDocument();
  });

  it("passes selected tags to createTask", async () => {
    const user = userEvent.setup();
    render(<TaskInput />);

    await user.type(screen.getByPlaceholderText("Task title..."), "Fix login issue");
    await user.click(screen.getByRole("button", { name: "bug" }));
    await user.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(mockCreateTask).toHaveBeenCalledWith(
        expect.objectContaining({ tags: ["bug"] })
      );
    });
  });

  it("omits tags when none are selected", async () => {
    const user = userEvent.setup();
    render(<TaskInput />);

    await user.type(screen.getByPlaceholderText("Task title..."), "Clean task");
    await user.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(mockCreateTask).toHaveBeenCalledWith(
        expect.objectContaining({ tags: undefined })
      );
    });
  });

  it("resets selected tags after a successful submission", async () => {
    const user = userEvent.setup();
    render(<TaskInput />);

    const bugChip = screen.getByRole("button", { name: "bug" });
    await user.click(bugChip);
    expect(bugChip).toHaveAttribute("aria-pressed", "true");

    await user.type(screen.getByPlaceholderText("Task title..."), "Reset tags");
    await user.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Task title...")).toHaveValue("");
    });
    expect(screen.getByRole("button", { name: "bug" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("clears selected tags when switching to manual mode", () => {
    render(<TaskInput />);

    const bugChip = screen.getByRole("button", { name: "bug" });
    fireEvent.click(bugChip);
    expect(bugChip).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: /Switch to manual mode/i }));
    fireEvent.click(screen.getByRole("button", { name: /Switch to AI mode/i }));

    expect(screen.getByRole("button", { name: "bug" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });
});

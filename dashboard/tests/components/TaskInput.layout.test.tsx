import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { TaskInput } from "../../features/tasks/components/TaskInput";
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

vi.mock("@/features/tasks/hooks/useTaskInputData", () => ({
  useTaskInputData: () => defaultHookData,
}));

vi.mock("@/components/ui/select", async () => import("../mocks/select-mock"));

vi.mock("@/hooks/useSelectableAgents", () => ({
  useSelectableAgents: () => [
    {
      name: "coder",
      displayName: "Coder Agent",
      role: "developer",
      enabled: true,
      status: "idle",
      skills: [],
    },
  ],
}));

vi.mock("@/components/BoardContext", () => ({
  useBoard: () => ({
    activeBoardId: undefined,
  }),
}));

describe("TaskInput layout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateTask.mockResolvedValue("task-123");
  });

  it("shows AI controls by default", () => {
    render(<TaskInput />);

    expect(screen.getByRole("combobox")).toHaveAttribute("data-selected-value", "auto");
    expect(screen.getByRole("button", { name: /Switch to manual mode/i })).toBeInTheDocument();
  });

  it("switches to manual mode and hides AI-only controls", () => {
    render(<TaskInput />);

    fireEvent.click(screen.getByRole("button", { name: /Switch to manual mode/i }));

    expect(screen.queryByText("Auto (Lead Agent)")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Switch to AI mode/i })).toBeInTheDocument();
  });

  it("restores AI controls when switching back from manual mode", () => {
    render(<TaskInput />);

    fireEvent.click(screen.getByRole("button", { name: /Switch to manual mode/i }));
    fireEvent.click(screen.getByRole("button", { name: /Switch to AI mode/i }));

    expect(screen.getByRole("combobox")).toHaveAttribute("data-selected-value", "auto");
    expect(screen.getByRole("button", { name: /Switch to manual mode/i })).toBeInTheDocument();
  });

  it("keeps attach and create actions visible in both modes", () => {
    render(<TaskInput />);

    expect(screen.getByText("Create")).toBeInTheDocument();
    expect(screen.getByLabelText("Attach files")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Switch to manual mode/i }));

    expect(screen.getByText("Create")).toBeInTheDocument();
    expect(screen.getByLabelText("Attach files")).toBeInTheDocument();
  });
});

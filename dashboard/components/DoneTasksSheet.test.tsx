import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { DoneTasksSheet } from "./DoneTasksSheet";

let mockDoneHistoryResult: unknown[] | undefined = [];
const mockRestoreMutation = vi.fn();

vi.mock("convex/react", () => ({
  useQuery: () => mockDoneHistoryResult,
  useMutation: () => mockRestoreMutation,
}));

function makeDoneTask(overrides: Record<string, unknown> = {}) {
  return {
    _id: `task_${Math.random().toString(36).slice(2)}`,
    _creationTime: 1000,
    title: "Completed task",
    status: "done",
    trustLevel: "autonomous",
    assignedAgent: "agent-alpha",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-15T10:30:00Z",
    ...overrides,
  };
}

describe("DoneTasksSheet", () => {
  afterEach(() => {
    cleanup();
    mockDoneHistoryResult = [];
    mockRestoreMutation.mockClear();
  });

  it("renders empty state when no done history", () => {
    mockDoneHistoryResult = [];
    render(<DoneTasksSheet open={true} onClose={() => {}} />);
    expect(screen.getByText("No completed tasks yet")).toBeInTheDocument();
  });

  it("renders task entries with title and agent name", () => {
    mockDoneHistoryResult = [
      makeDoneTask({ title: "Build feature X", assignedAgent: "coder-bot" }),
    ];
    render(<DoneTasksSheet open={true} onClose={() => {}} />);
    expect(screen.getByText("Build feature X")).toBeInTheDocument();
    expect(screen.getByText("coder-bot")).toBeInTheDocument();
  });

  it("shows 'On board' badge for active done tasks", () => {
    mockDoneHistoryResult = [makeDoneTask({ status: "done" })];
    render(<DoneTasksSheet open={true} onClose={() => {}} />);
    expect(screen.getByText("On board")).toBeInTheDocument();
  });

  it("shows 'Cleared' badge for soft-deleted done tasks", () => {
    mockDoneHistoryResult = [
      makeDoneTask({
        status: "deleted",
        previousStatus: "done",
        deletedAt: "2026-01-16T00:00:00Z",
      }),
    ];
    render(<DoneTasksSheet open={true} onClose={() => {}} />);
    expect(screen.getByText("Cleared")).toBeInTheDocument();
  });

  it("shows Restore button only for cleared tasks", () => {
    mockDoneHistoryResult = [
      makeDoneTask({ _id: "t1", title: "Active done", status: "done" }),
      makeDoneTask({
        _id: "t2",
        title: "Cleared done",
        status: "deleted",
        previousStatus: "done",
        deletedAt: "2026-01-16T00:00:00Z",
      }),
    ];
    render(<DoneTasksSheet open={true} onClose={() => {}} />);
    const restoreButtons = screen.getAllByRole("button", { name: /Restore/ });
    expect(restoreButtons).toHaveLength(1);
  });

  it("calls restore mutation when Restore is clicked", () => {
    mockDoneHistoryResult = [
      makeDoneTask({
        _id: "t_cleared",
        status: "deleted",
        previousStatus: "done",
        deletedAt: "2026-01-16T00:00:00Z",
      }),
    ];
    render(<DoneTasksSheet open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Restore/ }));
    expect(mockRestoreMutation).toHaveBeenCalledWith({
      taskId: "t_cleared",
      mode: "previous",
    });
  });

  it("shows loading state when query returns undefined", () => {
    mockDoneHistoryResult = undefined;
    render(<DoneTasksSheet open={true} onClose={() => {}} />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});

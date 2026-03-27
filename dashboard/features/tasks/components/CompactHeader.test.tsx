import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Doc, Id } from "@/convex/_generated/dataModel";
import { CompactHeader } from "./CompactHeader";

function makeTask(overrides: Partial<Doc<"tasks">> = {}): Doc<"tasks"> {
  return {
    _id: "task-1" as unknown as Doc<"tasks">["_id"],
    _creationTime: 1000,
    title: "Test task",
    status: "in_progress" as const,
    isManual: false,
    trustLevel: "autonomous" as const,
    tags: [],
    boardId: "board123" as Id<"boards">,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const defaultProps = {
  taskStatus: "in_progress",
  colors: null,
  tagColorMap: {} as Record<string, string>,
  canApprove: false,
  isPaused: false,
  isMergeLockedSource: false,
  viewMode: "thread" as const,
  onViewModeChange: vi.fn(),
  onApprove: vi.fn(),
  onToggleRejection: vi.fn(),
  onPause: vi.fn(),
  onResume: vi.fn(),
  onDeleteConfirmOpen: vi.fn(),
  onClose: vi.fn(),
};

describe("CompactHeader", () => {
  it("renders status dot and tags", () => {
    const task = makeTask({ tags: ["urgent", "frontend"] });
    render(
      <CompactHeader
        {...defaultProps}
        task={task}
        tagColorMap={{ urgent: "red", frontend: "blue" }}
      />,
    );

    expect(screen.getByTestId("status-dot")).toBeDefined();
    expect(screen.getByText("urgent")).toBeDefined();
    expect(screen.getByText("frontend")).toBeDefined();
  });

  it("shows approve/deny buttons when canApprove is true", () => {
    const task = makeTask({ status: "review", trustLevel: "human_approved" });
    render(<CompactHeader {...defaultProps} task={task} canApprove={true} />);

    expect(screen.getByTestId("approve-button")).toBeDefined();
    expect(screen.getByTestId("deny-button")).toBeDefined();
  });

  it("hides approve/deny when canApprove is false", () => {
    const task = makeTask({ status: "review" });
    render(<CompactHeader {...defaultProps} task={task} canApprove={false} />);

    expect(screen.queryByTestId("approve-button")).toBeNull();
    expect(screen.queryByTestId("deny-button")).toBeNull();
  });

  it("renders ViewToggle with correct value", () => {
    const task = makeTask();
    render(<CompactHeader {...defaultProps} task={task} viewMode="canvas" />);

    const canvasButton = screen.getByRole("button", { name: /canvas/i });
    expect(canvasButton).toBeDefined();
  });

  it("calls onClose when close button clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const task = makeTask();
    render(<CompactHeader {...defaultProps} task={task} onClose={onClose} />);

    await user.click(screen.getByTestId("close-button"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

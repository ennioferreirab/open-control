import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Doc, Id } from "@/convex/_generated/dataModel";
import { TaskCard } from "./TaskCard";

const approveTaskMock = vi.hoisted(() => vi.fn());
const approveAndKickOffTaskMock = vi.hoisted(() => vi.fn());
const softDeleteTaskMock = vi.hoisted(() => vi.fn());
const toggleFavoriteTaskMock = vi.hoisted(() => vi.fn());

vi.mock("@/features/tasks/hooks/useTaskCardActions", () => ({
  useTaskCardActions: () => ({
    approveTask: approveTaskMock,
    approveAndKickOffTask: approveAndKickOffTaskMock,
    softDeleteTask: softDeleteTaskMock,
    toggleFavoriteTask: toggleFavoriteTaskMock,
  }),
}));

// motion/react-client may rely on browser APIs; stub it minimally
vi.mock("motion/react-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react-client")>();
  return {
    ...actual,
    motion: {
      div: ({ children, ...rest }: React.PropsWithChildren<Record<string, unknown>>) => (
        <div {...(rest as React.HTMLAttributes<HTMLDivElement>)}>{children}</div>
      ),
    },
  };
});

vi.mock("motion/react", () => ({
  useReducedMotion: () => false,
}));

function makeTask(overrides: Partial<Doc<"tasks">> = {}): Doc<"tasks"> {
  return {
    _id: "task-1" as unknown as Doc<"tasks">["_id"],
    _creationTime: 1000,
    title: "Test task",
    status: "review" as const,
    isManual: false,
    trustLevel: "autonomous" as const,
    tags: [],
    boardId: "board123" as Id<"boards">,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("TaskCard — showApproveButton logic", () => {
  it("shows Approve button when status=review and isManual=false and awaitingKickoff is absent", () => {
    const task = makeTask({ awaitingKickoff: undefined });
    render(<TaskCard task={task} />);
    expect(screen.getByRole("button", { name: /approve/i })).toBeDefined();
  });

  it("shows Approve button when status=review and isManual=false and awaitingKickoff=false", () => {
    const task = makeTask({ awaitingKickoff: false });
    render(<TaskCard task={task} />);
    expect(screen.getByRole("button", { name: /approve/i })).toBeDefined();
  });

  it("does NOT show Approve button when awaitingKickoff=true", () => {
    const task = makeTask({ awaitingKickoff: true });
    render(<TaskCard task={task} />);
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
  });

  it("does NOT show Approve button when isManual=true (existing behavior)", () => {
    const task = makeTask({ isManual: true });
    render(<TaskCard task={task} />);
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
  });

  it("does NOT show Approve button when status is not review (existing behavior)", () => {
    const task = makeTask({ status: "in_progress" });
    render(<TaskCard task={task} />);
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
  });

  it("kicks off awaitingKickoff tasks directly from the badge without opening the card", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const executionPlan = {
      generatedAt: "2026-03-15T00:00:00Z",
      generatedBy: "workflow" as const,
      steps: [
        {
          tempId: "step_1",
          title: "Workflow step",
          description: "Execute workflow",
          assignedAgent: "nanobot",
          blockedBy: [],
          parallelGroup: 0,
          order: 0,
        },
      ],
    };

    render(
      <TaskCard
        task={makeTask({
          awaitingKickoff: true,
          executionPlan,
          workMode: "ai_workflow",
        })}
        onClick={onClick}
      />,
    );

    await user.click(screen.getByTestId("awaiting-kickoff-badge"));

    expect(approveAndKickOffTaskMock).toHaveBeenCalledWith("task-1", executionPlan);
    expect(onClick).not.toHaveBeenCalled();
  });
});

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { KanbanColumn } from "./KanbanColumn";

// Mock convex/react used by TaskCard
vi.mock("convex/react", () => ({
  useMutation: () => vi.fn(),
}));

// Mock motion/react used by TaskCard
vi.mock("motion/react", () => ({
  useReducedMotion: () => false,
}));

// Mock motion/react-client used by TaskCard
vi.mock("motion/react-client", () => ({
  div: ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) => {
    const { layoutId, layout, transition, ...rest } = props;
    void layoutId;
    void layout;
    void transition;
    return <div {...rest}>{children}</div>;
  },
}));

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    _id: `task_${Math.random().toString(36).slice(2)}`,
    _creationTime: 1000,
    title: "Test task",
    status: "review",
    trustLevel: "human_approved",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("KanbanColumn Clear button", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders Clear button when onClear is provided", () => {
    const tasks = [makeTask({ status: "done" })];
    render(
      <KanbanColumn
        title="Done"
        status="done"
        tasks={tasks as never}
        accentColor="bg-green-500"
        onClear={() => {}}
        clearDisabled={false}
      />
    );
    expect(screen.getByLabelText("Clear done tasks")).toBeInTheDocument();
  });

  it("does not render Clear button when onClear is not provided", () => {
    const tasks = [makeTask({ status: "done" })];
    render(
      <KanbanColumn
        title="Done"
        status="done"
        tasks={tasks as never}
        accentColor="bg-green-500"
      />
    );
    expect(screen.queryByLabelText("Clear done tasks")).not.toBeInTheDocument();
  });

  it("disables Clear button when clearDisabled is true", () => {
    render(
      <KanbanColumn
        title="Done"
        status="done"
        tasks={[] as never}
        accentColor="bg-green-500"
        onClear={() => {}}
        clearDisabled={true}
      />
    );
    const btn = screen.getByLabelText("Clear done tasks");
    expect(btn).toHaveClass("pointer-events-none", "opacity-40");
  });

  it("shows inline confirmation on Clear click and calls onClear on Yes", () => {
    const onClear = vi.fn();
    const tasks = [makeTask({ status: "done" })];
    render(
      <KanbanColumn
        title="Done"
        status="done"
        tasks={tasks as never}
        accentColor="bg-green-500"
        onClear={onClear}
        clearDisabled={false}
      />
    );
    fireEvent.click(screen.getByLabelText("Clear done tasks"));
    expect(screen.getByText("Clear all done tasks?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(onClear).toHaveBeenCalled();
  });

  it("hides inline confirmation on Cancel click", () => {
    const onClear = vi.fn();
    const tasks = [makeTask({ status: "done" })];
    render(
      <KanbanColumn
        title="Done"
        status="done"
        tasks={tasks as never}
        accentColor="bg-green-500"
        onClear={onClear}
        clearDisabled={false}
      />
    );
    fireEvent.click(screen.getByLabelText("Clear done tasks"));
    expect(screen.getByText("Clear all done tasks?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Clear all done tasks?")).not.toBeInTheDocument();
  });
});

describe("KanbanColumn View All button", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders View All button when onViewAll is provided", () => {
    const tasks = [makeTask({ status: "done" })];
    render(
      <KanbanColumn
        title="Done"
        status="done"
        tasks={tasks as never}
        accentColor="bg-green-500"
        onViewAll={() => {}}
      />
    );
    expect(screen.getByLabelText("View all done tasks")).toBeInTheDocument();
  });

  it("calls onViewAll when button is clicked", () => {
    const onViewAll = vi.fn();
    const tasks = [makeTask({ status: "done" })];
    render(
      <KanbanColumn
        title="Done"
        status="done"
        tasks={tasks as never}
        accentColor="bg-green-500"
        onViewAll={onViewAll}
      />
    );
    fireEvent.click(screen.getByLabelText("View all done tasks"));
    expect(onViewAll).toHaveBeenCalled();
  });
});

describe("KanbanColumn HITL badge", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders HITL badge with correct count when hitlCount > 0", () => {
    const tasks = [makeTask(), makeTask()];
    render(
      <KanbanColumn
        title="Review"
        status="review"
        tasks={tasks as never}
        accentColor="bg-amber-500"
        hitlCount={2}
      />
    );
    const badge = screen.getByTestId("hitl-badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("2");
  });

  it("hides badge when hitlCount is 0", () => {
    const tasks = [makeTask()];
    render(
      <KanbanColumn
        title="Review"
        status="review"
        tasks={tasks as never}
        accentColor="bg-amber-500"
        hitlCount={0}
      />
    );
    expect(screen.queryByTestId("hitl-badge")).not.toBeInTheDocument();
  });

  it("hides badge when hitlCount is not provided", () => {
    const tasks = [makeTask()];
    render(
      <KanbanColumn
        title="Review"
        status="review"
        tasks={tasks as never}
        accentColor="bg-amber-500"
      />
    );
    expect(screen.queryByTestId("hitl-badge")).not.toBeInTheDocument();
  });

  it("badge count matches the provided hitlCount, not total tasks", () => {
    // 3 tasks in the column but only 1 needing human approval
    const tasks = [
      makeTask({ trustLevel: "human_approved" }),
      makeTask({ trustLevel: "agent_reviewed" }),
      makeTask({ trustLevel: "autonomous" }),
    ];
    render(
      <KanbanColumn
        title="Review"
        status="review"
        tasks={tasks as never}
        accentColor="bg-amber-500"
        hitlCount={1}
      />
    );
    const badge = screen.getByTestId("hitl-badge");
    expect(badge).toHaveTextContent("1");
    // Total task count badge should show 3
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("has amber styling on the badge", () => {
    const tasks = [makeTask()];
    render(
      <KanbanColumn
        title="Review"
        status="review"
        tasks={tasks as never}
        accentColor="bg-amber-500"
        hitlCount={1}
      />
    );
    const badge = screen.getByTestId("hitl-badge");
    expect(badge.className).toContain("bg-amber-500");
    expect(badge.className).toContain("text-white");
  });
});

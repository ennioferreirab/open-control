import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { KanbanColumn } from "./KanbanColumn";
import { Id } from "../convex/_generated/dataModel";

vi.mock("motion/react-client", () => ({
  div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
    const { layoutId, layout, transition, ...rest } = props;
    void layoutId;
    void layout;
    void transition;
    return <div {...rest}>{children}</div>;
  },
}));

vi.mock("@/features/boards/hooks/useKanbanColumnInteractions", () => ({
  useKanbanColumnInteractions: () => ({
    moveStep: vi.fn(),
    moveTask: vi.fn(),
  }),
}));

vi.mock("convex/react", () => ({
  useMutation: () => vi.fn(),
}));

vi.mock("motion/react", () => ({
  useReducedMotion: () => false,
}));

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    _id: `task_${Math.random().toString(36).slice(2)}` as Id<"tasks">,
    _creationTime: 1000,
    title: "Test task",
    status: "inbox",
    trustLevel: "autonomous",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("KanbanColumn", () => {
  afterEach(() => {
    cleanup();
  });

  it("restores the light gray column background and border", () => {
    const { container } = render(
      <KanbanColumn
        title="Assigned"
        status="assigned"
        tasks={[]}
        stepGroups={[]}
        totalCount={0}
        accentColor="bg-cyan-500"
      />,
    );

    expect(screen.getByText("Assigned")).toBeInTheDocument();

    const column = container.firstElementChild;
    expect(column).not.toBeNull();
    expect(column?.className).toContain("bg-muted/40");
    expect(column?.className).toContain("border");
    expect(column?.className).toContain("border-border/70");
  });

  describe("collapsible step groups", () => {
    it("renders step groups collapsed by default", () => {
      const stepGroup = {
        taskId: "task_1" as Id<"tasks">,
        taskTitle: "My Task",
        steps: [
          {
            _id: "step_1" as Id<"steps">,
            _creationTime: 1000,
            taskId: "task_1" as Id<"tasks">,
            title: "Step 1",
            description: "desc",
            assignedAgent: "nanobot",
            status: "assigned",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
      };

      render(
        <KanbanColumn
          title="Assigned"
          status="assigned"
          tasks={[]}
          stepGroups={[stepGroup as never]}
          totalCount={1}
          accentColor="bg-cyan-500"
        />,
      );

      // Header should be visible
      expect(screen.getByText("My Task")).toBeInTheDocument();
      // Step content should NOT be visible (collapsed by default)
      expect(screen.queryByText("Step 1")).not.toBeInTheDocument();
    });

    it("expands step group on header click", () => {
      const stepGroup = {
        taskId: "task_1" as Id<"tasks">,
        taskTitle: "My Task",
        steps: [
          {
            _id: "step_1" as Id<"steps">,
            _creationTime: 1000,
            taskId: "task_1" as Id<"tasks">,
            title: "Step 1",
            description: "desc",
            assignedAgent: "nanobot",
            status: "assigned",
            blockedBy: [],
            parallelGroup: 1,
            order: 1,
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
      };

      render(
        <KanbanColumn
          title="Assigned"
          status="assigned"
          tasks={[]}
          stepGroups={[stepGroup as never]}
          totalCount={1}
          accentColor="bg-cyan-500"
        />,
      );

      // Click the header to expand
      fireEvent.click(screen.getByText("My Task"));
      // Step content should now be visible
      expect(screen.getByText("Step 1")).toBeInTheDocument();
    });
  });

  describe("collapsible tag groups", () => {
    it("renders tag groups collapsed by default", () => {
      const tagGroups = [
        {
          tag: "frontend",
          displayName: "frontend",
          tasks: [makeTask({ title: "Build UI" })],
        },
      ];

      render(
        <KanbanColumn
          title="Inbox"
          status="inbox"
          tasks={tagGroups[0].tasks as never[]}
          stepGroups={[]}
          tagGroups={tagGroups as never[]}
          totalCount={1}
          accentColor="bg-violet-500"
        />,
      );

      // Tag group header should be visible
      expect(screen.getByText("frontend")).toBeInTheDocument();
      // Task card should NOT be visible (collapsed by default)
      expect(screen.queryByText("Build UI")).not.toBeInTheDocument();
    });

    it("expands tag group on header click", () => {
      const tagGroups = [
        {
          tag: "frontend",
          displayName: "frontend",
          tasks: [makeTask({ title: "Build UI" })],
        },
      ];

      render(
        <KanbanColumn
          title="Inbox"
          status="inbox"
          tasks={tagGroups[0].tasks as never[]}
          stepGroups={[]}
          tagGroups={tagGroups as never[]}
          totalCount={1}
          accentColor="bg-violet-500"
        />,
      );

      fireEvent.click(screen.getByText("frontend"));
      expect(screen.getByText("Build UI")).toBeInTheDocument();
    });
  });
});

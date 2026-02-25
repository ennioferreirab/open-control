import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { PreKickoffModal } from "./PreKickoffModal";

// Mock Convex queries and mutations
const mockUseQuery = vi.fn();
vi.mock("convex/react", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
  useMutation: vi.fn(() => vi.fn()),
}));

vi.mock("@/convex/_generated/api", () => ({
  api: {
    tasks: {
      getById: "tasks:getById",
    },
    agents: {
      list: "agents:list",
    },
    messages: {
      listByTask: "messages:listByTask",
      listPlanChat: "messages:listPlanChat",
      postPlanChatMessage: "messages:postPlanChatMessage",
    },
  },
}));

// Mock dialog from Radix — render it inline for tests
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ open, onOpenChange, children }: { open: boolean; onOpenChange?: (open: boolean) => void; children: React.ReactNode }) =>
    open ? <div data-testid="dialog-root">{children}</div> : null,
  DialogContent: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div data-testid="dialog-content" className={className}>{children}</div>
  ),
  DialogTitle: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <h2 data-testid="dialog-title" className={className}>{children}</h2>
  ),
  DialogDescription: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <p data-testid="dialog-description" className={className}>{children}</p>
  ),
  DialogClose: ({ children, asChild }: { children: React.ReactNode; asChild?: boolean }) =>
    asChild ? <>{children}</> : <button>{children}</button>,
}));

// Mock PlanEditor (from story 4.2)
vi.mock("./PlanEditor", () => ({
  PlanEditor: ({ plan }: { plan: unknown; onPlanChange?: (p: unknown) => void }) => (
    <div data-testid="plan-editor">
      {plan ? "Plan loaded" : "No plan"}
    </div>
  ),
}));

// Mock ExecutionPlanTab (fallback for when PlanEditor is not available)
vi.mock("./ExecutionPlanTab", () => ({
  ExecutionPlanTab: ({ executionPlan }: { executionPlan: unknown; liveSteps?: unknown; isPlanning?: boolean }) => (
    <div data-testid="execution-plan-tab">
      {executionPlan ? "Plan loaded" : "No plan"}
    </div>
  ),
}));

// Mock PlanChatPanel (the chat component from story 4.5)
vi.mock("./PlanChatPanel", () => ({
  PlanChatPanel: ({ taskId }: { taskId: string }) => (
    <div data-testid="plan-chat-panel" data-task-id={taskId}>
      Chat panel
    </div>
  ),
}));

// Mock ScrollArea
vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div data-testid="scroll-area" className={className}>{children}</div>
  ),
}));

const mockTask = {
  _id: "task_1" as never,
  _creationTime: 1000,
  title: "My Supervised Task",
  status: "reviewing_plan",
  executionPlan: {
    steps: [
      {
        tempId: "step_1",
        title: "Step One",
        description: "Do something",
        assignedAgent: "general-agent",
        parallelGroup: 1,
        order: 1,
      },
    ],
    generatedAt: "2026-02-25T00:00:00Z",
    generatedBy: "lead-agent" as const,
  },
  trustLevel: "autonomous",
  supervisionMode: "supervised",
  createdAt: "2026-02-25T00:00:00Z",
  updatedAt: "2026-02-25T00:00:00Z",
};

describe("PreKickoffModal", () => {
  afterEach(() => {
    cleanup();
    mockUseQuery.mockReset();
    vi.clearAllMocks();
  });

  it("renders modal with task title and status badge when open", () => {
    mockUseQuery
      .mockReturnValueOnce(mockTask)  // tasks:getById
      .mockReturnValueOnce([]);       // agents:list

    render(
      <PreKickoffModal
        taskId={"task_1" as never}
        open={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText("My Supervised Task")).toBeInTheDocument();
    expect(screen.getByText("reviewing plan")).toBeInTheDocument();
  });

  it("renders two-panel layout with plan editor and chat headings", () => {
    mockUseQuery
      .mockReturnValueOnce(mockTask)
      .mockReturnValueOnce([]);

    render(
      <PreKickoffModal
        taskId={"task_1" as never}
        open={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText("Plan Editor")).toBeInTheDocument();
    expect(screen.getByText("Lead Agent Chat")).toBeInTheDocument();
  });

  it("renders PlanChatPanel in the right panel", () => {
    mockUseQuery
      .mockReturnValueOnce(mockTask)
      .mockReturnValueOnce([]);

    render(
      <PreKickoffModal
        taskId={"task_1" as never}
        open={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("plan-chat-panel")).toBeInTheDocument();
  });

  it("renders Kick-off button as disabled", () => {
    mockUseQuery
      .mockReturnValueOnce(mockTask)
      .mockReturnValueOnce([]);

    render(
      <PreKickoffModal
        taskId={"task_1" as never}
        open={true}
        onClose={vi.fn()}
      />
    );

    const kickoffButton = screen.getByRole("button", { name: /kick-off/i });
    expect(kickoffButton).toBeInTheDocument();
    expect(kickoffButton).toBeDisabled();
  });

  it("calls onClose when close button is clicked", () => {
    mockUseQuery
      .mockReturnValueOnce(mockTask)
      .mockReturnValueOnce([]);

    const onClose = vi.fn();
    render(
      <PreKickoffModal
        taskId={"task_1" as never}
        open={true}
        onClose={onClose}
      />
    );

    const closeButton = screen.getByRole("button", { name: /close/i });
    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not render when open is false", () => {
    mockUseQuery.mockReturnValue(undefined);

    render(
      <PreKickoffModal
        taskId={"task_1" as never}
        open={false}
        onClose={vi.fn()}
      />
    );

    expect(screen.queryByTestId("dialog-root")).toBeNull();
    expect(screen.queryByText("Plan Editor")).toBeNull();
  });
});

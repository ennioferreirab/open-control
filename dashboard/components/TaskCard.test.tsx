import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { TaskCard } from "./TaskCard";

// Mock motion/react-client to render plain divs
vi.mock("motion/react-client", () => ({
  div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
    const { layoutId, layout, transition, ...rest } = props;
    void layoutId;
    void layout;
    void transition;
    return <div {...rest}>{children}</div>;
  },
}));

// Mock motion/react hooks
vi.mock("motion/react", () => ({
  useReducedMotion: () => false,
  LayoutGroup: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

// Mock Convex
const mockApproveMutation = vi.fn();
vi.mock("convex/react", () => ({
  useQuery: () => [],
  useMutation: () => mockApproveMutation,
}));

const baseTask = {
  _id: "task1" as never,
  _creationTime: 1000,
  title: "Test task",
  status: "inbox" as const,
  trustLevel: "autonomous" as const,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("TaskCard", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the task title", () => {
    render(<TaskCard task={baseTask} />);
    expect(screen.getByText("Test task")).toBeInTheDocument();
  });

  it("renders description when provided", () => {
    render(
      <TaskCard task={{ ...baseTask, description: "A task description" }} />
    );
    expect(screen.getByText("A task description")).toBeInTheDocument();
  });

  it("does not render description when not provided", () => {
    render(<TaskCard task={baseTask} />);
    expect(screen.queryByText("A task description")).not.toBeInTheDocument();
  });

  it("renders the status badge", () => {
    render(<TaskCard task={baseTask} />);
    expect(screen.getByText("inbox")).toBeInTheDocument();
  });

  it("renders tags when provided", () => {
    render(<TaskCard task={{ ...baseTask, tags: ["urgent", "frontend"] }} />);
    expect(screen.getByText("urgent")).toBeInTheDocument();
    expect(screen.getByText("frontend")).toBeInTheDocument();
  });

  it("renders assigned agent name", () => {
    render(
      <TaskCard task={{ ...baseTask, assignedAgent: "agent-alpha" }} />
    );
    expect(screen.getByText("agent-alpha")).toBeInTheDocument();
  });

  it("has correct aria-label with title and status", () => {
    render(<TaskCard task={baseTask} />);
    expect(
      screen.getByRole("article", { name: "Test task - inbox" })
    ).toBeInTheDocument();
  });

  it("applies violet border for inbox status", () => {
    render(<TaskCard task={baseTask} />);
    const card = screen.getByRole("article");
    expect(card.className).toContain("border-l-violet-500");
  });

  it("applies blue border for in_progress status", () => {
    render(
      <TaskCard task={{ ...baseTask, status: "in_progress" }} />
    );
    const card = screen.getByRole("article");
    expect(card.className).toContain("border-l-blue-500");
  });

  it("applies green border for done status", () => {
    render(<TaskCard task={{ ...baseTask, status: "done" }} />);
    const card = screen.getByRole("article");
    expect(card.className).toContain("border-l-green-500");
  });

  it("applies red border for crashed status", () => {
    render(<TaskCard task={{ ...baseTask, status: "crashed" }} />);
    const card = screen.getByRole("article");
    expect(card.className).toContain("border-l-red-500");
  });

  // --- Story 5.1: Review indicator ---

  it("does not show review indicator for autonomous tasks", () => {
    render(<TaskCard task={baseTask} />);
    expect(screen.queryByText("HITL")).not.toBeInTheDocument();
  });

  it("shows HITL badge for human_approved tasks", () => {
    render(
      <TaskCard task={{ ...baseTask, trustLevel: "human_approved" }} />
    );
    expect(screen.getByText("HITL")).toBeInTheDocument();
  });

  // --- Story 6.1: Approve button ---

  it("shows Approve button for human_approved tasks in review", () => {
    render(
      <TaskCard
        task={{ ...baseTask, status: "review", trustLevel: "human_approved" }}
      />
    );
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("does not show Approve button for autonomous tasks in review", () => {
    render(
      <TaskCard
        task={{ ...baseTask, status: "review", trustLevel: "autonomous" }}
      />
    );
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("does not show Approve button for human_approved tasks not in review", () => {
    render(
      <TaskCard
        task={{ ...baseTask, status: "in_progress", trustLevel: "human_approved" }}
      />
    );
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("calls approveMutation with correct taskId when Approve is clicked", () => {
    mockApproveMutation.mockClear();
    const onClick = vi.fn();
    render(
      <TaskCard
        task={{ ...baseTask, status: "review", trustLevel: "human_approved" }}
        onClick={onClick}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(mockApproveMutation).toHaveBeenCalledWith({ taskId: "task1" });
    // stopPropagation should prevent parent onClick
    expect(onClick).not.toHaveBeenCalled();
  });

  // --- Story 7.1: Awaiting Kick-off badge (AC: 6.2) ---

  it("shows Awaiting Kick-off badge when task is in review with awaitingKickoff=true", () => {
    render(
      <TaskCard
        task={{ ...baseTask, status: "review", awaitingKickoff: true } as never}
      />
    );
    expect(screen.getByTestId("awaiting-kickoff-badge")).toBeInTheDocument();
    expect(screen.getByText("Awaiting Kick-off")).toBeInTheDocument();
  });

  it("does not show Awaiting Kick-off badge for review tasks without awaitingKickoff", () => {
    render(
      <TaskCard task={{ ...baseTask, status: "review" }} />
    );
    expect(screen.queryByTestId("awaiting-kickoff-badge")).not.toBeInTheDocument();
  });

  it("does not show regular status badge when awaitingKickoff=true (badge is suppressed)", () => {
    render(
      <TaskCard
        task={{ ...baseTask, status: "review", awaitingKickoff: true } as never}
      />
    );
    // The regular review status badge is hidden when awaitingKickoff=true
    const badges = screen.queryAllByText("review");
    expect(badges).toHaveLength(0);
  });

  // --- Story 7.4: Paused badge ---

  it("shows Paused badge when task is in review without awaitingKickoff (AC 6)", () => {
    render(
      <TaskCard task={{ ...baseTask, status: "review" }} />
    );
    expect(screen.getByTestId("paused-badge")).toBeInTheDocument();
    expect(screen.getByText("Paused")).toBeInTheDocument();
  });

  it("does NOT show Paused badge when task has awaitingKickoff=true (AC 6)", () => {
    render(
      <TaskCard
        task={{ ...baseTask, status: "review", awaitingKickoff: true } as never}
      />
    );
    expect(screen.queryByTestId("paused-badge")).not.toBeInTheDocument();
  });

  it("does NOT show Paused badge for non-review tasks (AC 6)", () => {
    render(<TaskCard task={{ ...baseTask, status: "in_progress" }} />);
    expect(screen.queryByTestId("paused-badge")).not.toBeInTheDocument();
  });

  it("suppresses regular status badge for all review tasks (AC 6)", () => {
    render(
      <TaskCard task={{ ...baseTask, status: "review" }} />
    );
    // The regular status badge showing "review" text must not appear
    const reviewBadges = screen.queryAllByText("review");
    expect(reviewBadges).toHaveLength(0);
  });

  it("suppresses regular status badge for review+awaitingKickoff tasks (AC 6)", () => {
    render(
      <TaskCard
        task={{ ...baseTask, status: "review", awaitingKickoff: true } as never}
      />
    );
    const reviewBadges = screen.queryAllByText("review");
    expect(reviewBadges).toHaveLength(0);
  });

  // --- Story 5.5: File indicator ---

  it("shows paperclip icon and file count when files present", () => {
    render(
      <TaskCard
        task={{
          ...baseTask,
          files: [
            {
              name: "a.pdf",
              type: "application/pdf",
              size: 100,
              subfolder: "attachments",
              uploadedAt: "2026-01-01T00:00:00Z",
            },
          ],
        }}
      />
    );
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("does not show file count when no files", () => {
    render(<TaskCard task={baseTask} />);
    // baseTask has no files field — ensure no numeric count is displayed in a file span
    const card = screen.getByRole("article");
    const fileSpans = card.querySelectorAll("span.inline-flex");
    const fileIndicator = Array.from(fileSpans).find(
      (span) => span.querySelector("svg") && /^\d+$/.test(span.textContent?.trim() ?? "")
    );
    expect(fileIndicator).toBeUndefined();
  });

  it("shows correct count for multiple files", () => {
    render(
      <TaskCard
        task={{
          ...baseTask,
          files: [
            {
              name: "a.pdf",
              type: "application/pdf",
              size: 100,
              subfolder: "attachments",
              uploadedAt: "2026-01-01T00:00:00Z",
            },
            {
              name: "b.csv",
              type: "text/csv",
              size: 200,
              subfolder: "attachments",
              uploadedAt: "2026-01-01T00:00:00Z",
            },
            {
              name: "c.txt",
              type: "text/plain",
              size: 50,
              subfolder: "attachments",
              uploadedAt: "2026-01-01T00:00:00Z",
            },
          ],
        }}
      />
    );
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});

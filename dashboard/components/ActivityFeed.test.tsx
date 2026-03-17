import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ActivityFeed } from "./ActivityFeed";
import { FeedItem } from "./FeedItem";
import type { Doc } from "@/convex/_generated/dataModel";

// Stub scrollTo for jsdom
beforeEach(() => {
  Element.prototype.scrollTo = vi.fn();
});

// Mock convex/react
const mockUseQuery = vi.fn();
vi.mock("convex/react", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}));

// Mock motion/react to render plain divs (avoids animation complexity in tests)
vi.mock("motion/react", () => ({
  motion: {
    div: ({
      children,
      ...props
    }: React.PropsWithChildren<Record<string, unknown>>) => {
      const {
        initial: _initial,
        animate: _animate,
        transition: _transition,
        ...htmlProps
      } = props;
      return <div {...htmlProps}>{children}</div>;
    },
  },
}));

// Mock ShadCN ScrollArea to render a plain div (avoids Radix internals in tests)
vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) => {
    const { className, ...rest } = props;
    return (
      <div className={className as string} {...rest}>
        {children}
      </div>
    );
  },
}));

type Activity = Doc<"activities">;

function makeActivity(overrides: Partial<Activity> = {}): Activity {
  return {
    _id: "act1" as Activity["_id"],
    _creationTime: 1708700000000,
    taskId: undefined,
    agentName: "agent-1",
    eventType: "task_created",
    description: "Created task: Setup CI",
    timestamp: "2026-02-23T14:32:05.000Z",
    ...overrides,
  } as Activity;
}

describe("ActivityFeed", () => {
  afterEach(() => {
    cleanup();
    mockUseQuery.mockReset();
  });

  it("shows empty state when no activities exist", () => {
    mockUseQuery.mockReturnValue([]);
    render(<ActivityFeed />);
    expect(screen.getByText("Waiting for activity...")).toBeInTheDocument();
  });

  it("renders nothing while loading", () => {
    mockUseQuery.mockReturnValue(undefined);
    const { container } = render(<ActivityFeed />);
    expect(container.innerHTML).toBe("");
  });

  it("shows reconnecting message when data disappears after initial load", () => {
    // First render with data to set hadDataRef
    mockUseQuery.mockReturnValue([makeActivity()]);
    const { rerender } = render(<ActivityFeed />);

    // Simulate WebSocket disconnection
    mockUseQuery.mockReturnValue(undefined);
    rerender(<ActivityFeed />);

    expect(screen.getByText("Reconnecting...")).toBeInTheDocument();
  });

  it("renders activities in newest-first order", () => {
    // listRecent returns newest-first (desc order)
    mockUseQuery.mockReturnValue([
      makeActivity({
        _id: "act3" as Activity["_id"],
        timestamp: "2026-02-23T14:34:15.000Z",
        description: "Third event",
      }),
      makeActivity({
        _id: "act2" as Activity["_id"],
        timestamp: "2026-02-23T14:33:10.000Z",
        description: "Second event",
      }),
      makeActivity({
        _id: "act1" as Activity["_id"],
        timestamp: "2026-02-23T14:32:05.000Z",
        description: "First event",
      }),
    ]);
    render(<ActivityFeed />);

    const items = screen.getAllByText(/event/);
    expect(items[0].textContent).toBe("Third event");
    expect(items[1].textContent).toBe("Second event");
    expect(items[2].textContent).toBe("First event");
  });

  it("shows 'Showing last 100 activities' when feed is at capacity", () => {
    const hundredActivities = Array.from({ length: 100 }, (_, i) =>
      makeActivity({
        _id: `act${i}` as Activity["_id"],
        description: `Event ${i}`,
      })
    );
    mockUseQuery.mockReturnValue(hundredActivities);
    render(<ActivityFeed />);
    expect(screen.getByText("Showing last 100 activities")).toBeInTheDocument();
  });
});

describe("FeedItem", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders timestamp, agent name, and description", () => {
    const activity = makeActivity();
    render(<FeedItem activity={activity} />);

    expect(screen.getByText("agent-1")).toBeInTheDocument();
    expect(screen.getByText("Created task: Setup CI")).toBeInTheDocument();
  });

  it("renders red left border for error events", () => {
    const errorEvents = ["task_crashed", "system_error", "agent_crashed"] as const;
    for (const eventType of errorEvents) {
      cleanup();
      const activity = makeActivity({
        _id: `err-${eventType}` as Activity["_id"],
        eventType,
      });
      const { container } = render(<FeedItem activity={activity} />);
      const item = container.firstChild as HTMLElement;
      expect(item.className).toContain("border-red-400");
    }
  });

  it("renders amber left border for HITL events", () => {
    const hitlEvents = ["hitl_requested", "hitl_approved", "hitl_denied"] as const;
    for (const eventType of hitlEvents) {
      cleanup();
      const activity = makeActivity({
        _id: `hitl-${eventType}` as Activity["_id"],
        eventType,
      });
      const { container } = render(<FeedItem activity={activity} />);
      const item = container.firstChild as HTMLElement;
      expect(item.className).toContain("border-amber-400");
    }
  });

  it("renders transparent left border for normal events", () => {
    const activity = makeActivity({ eventType: "task_created" });
    const { container } = render(<FeedItem activity={activity} />);
    const item = container.firstChild as HTMLElement;
    expect(item.className).toContain("border-transparent");
    expect(item.className).not.toContain("border-red-400");
    expect(item.className).not.toContain("border-amber-400");
  });

  it("does not render agent name when absent", () => {
    const activity = makeActivity({ agentName: undefined });
    render(<FeedItem activity={activity} />);
    expect(screen.queryByText("agent-1")).not.toBeInTheDocument();
  });
});

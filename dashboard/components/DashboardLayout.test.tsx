import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import type { GatewaySleepRuntime } from "@/lib/gatewaySleepRuntime";

const mockUseGatewaySleepRuntime = vi.fn<() => GatewaySleepRuntime | null | undefined>(() => null);
const mockUseGatewaySleepCountdown = vi.fn<(runtime?: GatewaySleepRuntime | null) => string | null>(
  () => null,
);
const mockGatewaySleepMutation = vi.fn().mockResolvedValue(undefined);

function makeRuntime(overrides: Partial<GatewaySleepRuntime>): GatewaySleepRuntime {
  return {
    mode: "active",
    pollIntervalSeconds: 5,
    manualRequested: false,
    reason: "startup",
    lastTransitionAt: "2026-03-11T00:00:00.000Z",
    ...overrides,
  };
}

// Mock heavy child components to avoid loading entire dependency tree
vi.mock("@/features/agents/components/AgentSidebar", () => ({
  AgentSidebar: () => <div data-testid="agent-sidebar">Agents</div>,
}));

vi.mock("@/features/activity/components/ActivityFeedPanel", () => ({
  ActivityFeedPanel: () => (
    <div data-testid="activity-feed-panel">
      <span>Activity Feed</span>
      <span>Waiting for activity...</span>
    </div>
  ),
}));

vi.mock("@/features/tasks/components/TaskInput", () => ({
  TaskInput: () => <div data-testid="task-input">Task Input</div>,
}));

vi.mock("@/features/search/components/SearchBar", () => ({
  SearchBar: () => <div data-testid="search-bar">Search Bar</div>,
}));

vi.mock("@/features/boards/components/KanbanBoard", () => ({
  KanbanBoard: ({ onTaskClick }: { onTaskClick?: (id: string) => void }) => (
    <div data-testid="kanban-board" onClick={() => onTaskClick?.("task1")}>
      No tasks yet. Type above to create your first task.
    </div>
  ),
}));

vi.mock("@/features/tasks/components/TaskDetailSheet", () => ({
  TaskDetailSheet: ({ taskId, onClose }: { taskId: string | null; onClose: () => void }) =>
    taskId ? (
      <div data-testid="task-detail-sheet" onClick={onClose}>
        Detail
      </div>
    ) : null,
}));

vi.mock("@/features/settings/components/SettingsPanel", () => ({
  SettingsPanel: () => <div data-testid="settings-panel">Settings</div>,
}));

vi.mock("@/features/terminal/components/TerminalBoard", () => ({
  TerminalBoard: () => <div data-testid="terminal-board">Terminal Board</div>,
}));

vi.mock("@/components/BoardContext", () => ({
  BoardProvider: ({ children }: React.PropsWithChildren) => <>{children}</>,
  useBoard: () => ({ openTerminals: [] }),
}));

vi.mock("@/features/boards/components/BoardSelector", () => ({
  BoardSelector: ({ onOpenSettings }: { onOpenSettings?: () => void }) => (
    <button data-testid="board-selector" onClick={() => onOpenSettings?.()}>
      Board Selector
    </button>
  ),
}));

vi.mock("@/features/boards/components/BoardSettingsSheet", () => ({
  BoardSettingsSheet: () => null,
}));

vi.mock("@/components/CronJobsModal", () => ({
  CronJobsModal: () => null,
}));

vi.mock("@/hooks/useGatewaySleepRuntime", () => ({
  useGatewaySleepRuntime: () => mockUseGatewaySleepRuntime(),
  useGatewaySleepCountdown: () => mockUseGatewaySleepCountdown(),
}));

vi.mock("@/features/settings/hooks/useGatewaySleepModeRequest", () => ({
  useGatewaySleepModeRequest: () => mockGatewaySleepMutation,
}));

// Mock ShadCN sidebar
vi.mock("@/components/ui/sidebar", () => ({
  SidebarProvider: ({ children }: React.PropsWithChildren) => (
    <div data-testid="sidebar-provider">{children}</div>
  ),
  SidebarInset: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SidebarTrigger: () => <button>Toggle Sidebar</button>,
}));

// Mock ShadCN sheet
vi.mock("@/components/ui/sheet", () => ({
  Sheet: ({ children, open }: React.PropsWithChildren<{ open: boolean }>) =>
    open ? <div data-testid="settings-sheet">{children}</div> : null,
  SheetContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SheetHeader: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SheetTitle: ({ children }: React.PropsWithChildren) => <h2>{children}</h2>,
  SheetDescription: ({ children }: React.PropsWithChildren) => <p>{children}</p>,
}));

// Mock matchMedia for controlling viewport breakpoints
function createMatchMedia(width: number) {
  return (query: string): MediaQueryList => {
    const listeners: Array<(e: MediaQueryListEvent) => void> = [];
    return {
      matches: (() => {
        const match = query.match(/\(min-width:\s*(\d+)px\)/);
        if (match) return width >= parseInt(match[1]);
        const maxMatch = query.match(/\(max-width:\s*(\d+)px\)/);
        if (maxMatch) return width <= parseInt(maxMatch[1]);
        return false;
      })(),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => listeners.push(cb),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    } as unknown as MediaQueryList;
  };
}

// Cookie mock
Object.defineProperty(document, "cookie", {
  writable: true,
  value: "",
});

// Import AFTER mocks are set up
import { DashboardLayout } from "./DashboardLayout";

describe("DashboardLayout", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.restoreAllMocks();
    mockUseGatewaySleepRuntime.mockReturnValue(null);
    mockUseGatewaySleepCountdown.mockReturnValue(null);
    mockGatewaySleepMutation.mockClear();
  });

  it("renders dashboard content when width < 1024px", () => {
    window.matchMedia = createMatchMedia(800);
    render(<DashboardLayout />);
    expect(screen.getByText("Open Control")).toBeInTheDocument();
  });

  it("renders the Open Control title on desktop", () => {
    window.matchMedia = createMatchMedia(1280);
    render(<DashboardLayout />);
    expect(screen.getByText("Open Control")).toBeInTheDocument();
  });

  it("renders the sidebar on desktop", () => {
    window.matchMedia = createMatchMedia(1280);
    render(<DashboardLayout />);
    expect(screen.getByTestId("agent-sidebar")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
  });

  it("renders the activity feed panel on desktop", () => {
    window.matchMedia = createMatchMedia(1280);
    render(<DashboardLayout />);
    expect(screen.getByTestId("activity-feed-panel")).toBeInTheDocument();
    expect(screen.getByText("Activity Feed")).toBeInTheDocument();
    expect(screen.getByText("Waiting for activity...")).toBeInTheDocument();
  });

  it("renders the kanban board empty state on desktop", () => {
    window.matchMedia = createMatchMedia(1280);
    render(<DashboardLayout />);
    expect(screen.getByTestId("kanban-board")).toBeInTheDocument();
    expect(
      screen.getByText("No tasks yet. Type above to create your first task."),
    ).toBeInTheDocument();
  });

  it("renders the task input on desktop", () => {
    window.matchMedia = createMatchMedia(1280);
    render(<DashboardLayout />);
    expect(screen.getByTestId("task-input")).toBeInTheDocument();
  });

  it("renders the search input in header on desktop", () => {
    window.matchMedia = createMatchMedia(1280);
    render(<DashboardLayout />);
    expect(screen.getByTestId("search-bar")).toBeInTheDocument();
  });

  it("does not render settings sheet by default", () => {
    window.matchMedia = createMatchMedia(1280);
    render(<DashboardLayout />);
    expect(screen.queryByTestId("settings-sheet")).not.toBeInTheDocument();
  });

  it("opens settings sheet when settings button is clicked", () => {
    window.matchMedia = createMatchMedia(1280);
    render(<DashboardLayout />);

    const settingsButton = screen.getByLabelText("Open settings");
    fireEvent.click(settingsButton);

    expect(screen.getByTestId("settings-sheet")).toBeInTheDocument();
    expect(screen.getByTestId("settings-panel")).toBeInTheDocument();
  });

  it("renders sleeping gateway badge and wake button when runtime reports sleep", () => {
    window.matchMedia = createMatchMedia(1280);
    mockUseGatewaySleepRuntime.mockReturnValue(
      makeRuntime({
        mode: "sleep",
        pollIntervalSeconds: 300,
        manualRequested: true,
        reason: "manual",
      }),
    );

    render(<DashboardLayout />);

    expect(screen.getByText("Gateway sleeping · 300s")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Wake now" })).toBeInTheDocument();
  });

  it("renders active gateway badge and sleep button when runtime reports active", () => {
    window.matchMedia = createMatchMedia(1280);
    mockUseGatewaySleepRuntime.mockReturnValue(
      makeRuntime({
        mode: "active",
        pollIntervalSeconds: 5,
        manualRequested: false,
        reason: "startup",
      }),
    );

    render(<DashboardLayout />);

    expect(screen.getByText("Gateway active · 5s")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sleep now" })).toBeInTheDocument();
  });

  it("requests manual wake from the header button", () => {
    window.matchMedia = createMatchMedia(1280);
    mockUseGatewaySleepRuntime.mockReturnValue(
      makeRuntime({
        mode: "sleep",
        pollIntervalSeconds: 300,
        manualRequested: true,
        reason: "manual",
      }),
    );

    render(<DashboardLayout />);

    fireEvent.click(screen.getByRole("button", { name: "Wake now" }));

    expect(mockGatewaySleepMutation).toHaveBeenCalledWith({ mode: "active" });
  });

  it("shows countdown in sleep mode badge", () => {
    window.matchMedia = createMatchMedia(1280);
    mockUseGatewaySleepRuntime.mockReturnValue(
      makeRuntime({
        mode: "sleep",
        pollIntervalSeconds: 300,
        manualRequested: false,
        reason: "idle",
      }),
    );
    mockUseGatewaySleepCountdown.mockReturnValue("4:32");

    render(<DashboardLayout />);

    expect(screen.getByText("Gateway sleeping · sync in 4:32")).toBeInTheDocument();
  });

  it("shows countdown in active mode badge", () => {
    window.matchMedia = createMatchMedia(1280);
    mockUseGatewaySleepRuntime.mockReturnValue(
      makeRuntime({
        mode: "active",
        pollIntervalSeconds: 5,
        manualRequested: false,
        reason: "work_found",
      }),
    );
    mockUseGatewaySleepCountdown.mockReturnValue("3:15");

    render(<DashboardLayout />);

    expect(screen.getByText("Gateway active · sleep in 3:15")).toBeInTheDocument();
  });

  it("falls back to pollIntervalSeconds when countdown is null", () => {
    window.matchMedia = createMatchMedia(1280);
    mockUseGatewaySleepRuntime.mockReturnValue(
      makeRuntime({
        mode: "active",
        pollIntervalSeconds: 5,
        manualRequested: true,
        reason: "manual",
      }),
    );
    mockUseGatewaySleepCountdown.mockReturnValue(null);

    render(<DashboardLayout />);

    expect(screen.getByText("Gateway active · 5s")).toBeInTheDocument();
  });
});

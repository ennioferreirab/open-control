import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// Mock heavy child components to avoid loading entire dependency tree
vi.mock("@/components/AgentSidebar", () => ({
  AgentSidebar: () => <div data-testid="agent-sidebar">Agents</div>,
}));

vi.mock("@/components/ActivityFeedPanel", () => ({
  ActivityFeedPanel: () => (
    <div data-testid="activity-feed-panel">
      <span>Activity Feed</span>
      <span>Waiting for activity...</span>
    </div>
  ),
}));

vi.mock("@/components/TaskInput", () => ({
  TaskInput: () => <div data-testid="task-input">Task Input</div>,
}));

vi.mock("@/components/SearchBar", () => ({
  SearchBar: () => <div data-testid="search-bar">Search Bar</div>,
}));

vi.mock("@/components/KanbanBoard", () => ({
  KanbanBoard: ({ onTaskClick }: { onTaskClick?: (id: string) => void }) => (
    <div data-testid="kanban-board" onClick={() => onTaskClick?.("task1")}>
      No tasks yet. Type above to create your first task.
    </div>
  ),
}));

vi.mock("@/components/TaskDetailSheet", () => ({
  TaskDetailSheet: ({ taskId, onClose }: { taskId: string | null; onClose: () => void }) => (
    taskId ? <div data-testid="task-detail-sheet" onClick={onClose}>Detail</div> : null
  ),
}));

vi.mock("@/components/SettingsPanel", () => ({
  SettingsPanel: () => <div data-testid="settings-panel">Settings</div>,
}));

vi.mock("@/components/BoardContext", () => ({
  BoardProvider: ({ children }: React.PropsWithChildren) => <>{children}</>,
  useBoard: () => ({ openTerminals: [] }),
}));

vi.mock("@/components/BoardSelector", () => ({
  BoardSelector: ({ onOpenSettings }: { onOpenSettings?: () => void }) => (
    <button data-testid="board-selector" onClick={() => onOpenSettings?.()}>
      Board Selector
    </button>
  ),
}));

vi.mock("@/components/BoardSettingsSheet", () => ({
  BoardSettingsSheet: () => null,
}));

vi.mock("@/components/CronJobsModal", () => ({
  CronJobsModal: () => null,
}));

// Mock ShadCN sidebar
vi.mock("@/components/ui/sidebar", () => ({
  SidebarProvider: ({ children }: React.PropsWithChildren) => <div data-testid="sidebar-provider">{children}</div>,
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
      addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) =>
        listeners.push(cb),
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
  });

  it("renders dashboard content when width < 1024px", () => {
    window.matchMedia = createMatchMedia(800);
    render(<DashboardLayout />);
    expect(screen.getByText("Mission Control")).toBeInTheDocument();
  });

  it("renders the Mission Control title on desktop", () => {
    window.matchMedia = createMatchMedia(1280);
    render(<DashboardLayout />);
    expect(screen.getByText("Mission Control")).toBeInTheDocument();
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
      screen.getByText("No tasks yet. Type above to create your first task.")
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
});

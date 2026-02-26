import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const user = userEvent.setup({ delay: null });

// Mock convex/react hooks
vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    tasks: {
      getById: "tasks:getById",
      approve: "tasks:approve",
      approveAndKickOff: "tasks:approveAndKickOff",
      pauseTask: "tasks:pauseTask",
      resumeTask: "tasks:resumeTask",
      retry: "tasks:retry",
      updateTags: "tasks:updateTags",
      addTaskFiles: "tasks:addTaskFiles",
      removeTaskFile: "tasks:removeTaskFile",
    },
    messages: { listByTask: "messages:listByTask" },
    steps: { getByTask: "steps:getByTask" },
    activities: { create: "activities:create" },
    taskTags: { list: "taskTags:list" },
  },
}));

// Mock child components that are not relevant to tag editing
vi.mock("../../components/ThreadMessage", () => ({
  ThreadMessage: () => null,
}));
vi.mock("../../components/ExecutionPlanTab", () => ({
  ExecutionPlanTab: () => null,
}));
vi.mock("../../components/InlineRejection", () => ({
  InlineRejection: () => null,
}));
vi.mock("../../components/DocumentViewerModal", () => ({
  DocumentViewerModal: () => null,
}));
vi.mock("../../components/ThreadInput", () => ({
  ThreadInput: () => null,
}));

// Mock motion/react-client (default export with div)
vi.mock("motion/react-client", () => ({
  __esModule: true,
  default: { div: "div" },
  div: "div",
}));
vi.mock("motion/react", () => ({
  useReducedMotion: () => false,
}));

// Mock Radix Popover to be testable in jsdom
vi.mock("@/components/ui/popover", () => {
  const React = require("react");
  return {
    Popover: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    PopoverTrigger: React.forwardRef(
      (
        { children, asChild, ...props }: any,
        ref: any
      ) => {
        if (asChild && React.isValidElement(children)) {
          return React.cloneElement(children, { ...props, ref });
        }
        return <button {...props} ref={ref}>{children}</button>;
      }
    ),
    PopoverContent: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="tag-popover-content">{children}</div>
    ),
  };
});

// Mock Sheet components
vi.mock("@/components/ui/sheet", () => {
  const React = require("react");
  return {
    Sheet: ({ children, open }: any) => open ? <div data-testid="sheet">{children}</div> : null,
    SheetContent: ({ children }: any) => <div>{children}</div>,
    SheetHeader: ({ children }: any) => <div>{children}</div>,
    SheetTitle: ({ children }: any) => <div>{children}</div>,
    SheetDescription: ({ children, asChild }: any) => asChild ? <>{children}</> : <div>{children}</div>,
  };
});

vi.mock("@/components/ui/tabs", () => {
  const React = require("react");
  function Tabs({ children, value, onValueChange }: any) {
    return <div data-testid="tabs" data-value={value}>{children}</div>;
  }
  function TabsList({ children }: any) { return <div>{children}</div>; }
  function TabsTrigger({ children, value }: any) {
    return <button data-value={value}>{children}</button>;
  }
  function TabsContent({ children, value }: any) {
    return <div data-testid={`tab-${value}`}>{children}</div>;
  }
  return { Tabs, TabsList, TabsTrigger, TabsContent };
});

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children, ...props }: any) => <span {...props}>{children}</span>,
}));
vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
}));
vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({ children }: any) => <div>{children}</div>,
}));
vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}));

import { useQuery, useMutation } from "convex/react";
import { TaskDetailSheet } from "../../components/TaskDetailSheet";

const mockUseQuery = useQuery as ReturnType<typeof vi.fn>;
const mockUseMutation = useMutation as ReturnType<typeof vi.fn>;

const SAMPLE_TAGS_CATALOG = [
  { _id: "t1", name: "bug", color: "red" },
  { _id: "t2", name: "feature", color: "blue" },
  { _id: "t3", name: "urgent", color: "amber" },
];

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    _id: "task1" as any,
    _creationTime: 1700000000000,
    title: "Test Task",
    status: "in_progress",
    assignedAgent: "dev-agent",
    trustLevel: "autonomous",
    tags: ["bug", "feature"],
    createdAt: "2024-01-01T00:00:00.000Z",
    updatedAt: "2024-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("TaskDetailSheet — tag editing (Story 9-3)", () => {
  const mockUpdateTags = vi.fn();
  const noop = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUpdateTags.mockResolvedValue(undefined);
    mockUseMutation.mockImplementation((ref: string) => {
      if (String(ref).includes("updateTags")) return mockUpdateTags;
      return noop;
    });
  });

  function renderSheet(taskOverrides: Record<string, unknown> = {}) {
    const task = makeTask(taskOverrides);
    mockUseQuery.mockImplementation((ref: string) => {
      if (String(ref).includes("getById")) return task;
      if (String(ref).includes("listByTask")) return [];
      if (String(ref).includes("getByTask")) return [];
      if (String(ref).includes("taskTags")) return SAMPLE_TAGS_CATALOG;
      return undefined;
    });
    render(<TaskDetailSheet taskId={"task1" as any} onClose={vi.fn()} />);
    return task;
  }

  // AC2: Tag chips with X button
  it("renders tag chips with remove buttons", () => {
    renderSheet();
    const configTab = screen.getByTestId("tab-config");
    // Tags appear in both chip and popover; assert via the remove buttons which are unique to chips
    expect(within(configTab).getByLabelText("Remove tag bug")).toBeInTheDocument();
    expect(within(configTab).getByLabelText("Remove tag feature")).toBeInTheDocument();
  });

  // AC2: Clicking X removes the tag
  it("calls updateTags without the removed tag when X is clicked", async () => {
    renderSheet();
    const configTab = screen.getByTestId("tab-config");
    await user.click(within(configTab).getByLabelText("Remove tag bug"));
    expect(mockUpdateTags).toHaveBeenCalledWith({
      taskId: "task1",
      tags: ["feature"],
    });
  });

  // AC3: Add tag button exists
  it("shows an Add tag button", () => {
    renderSheet();
    const configTab = screen.getByTestId("tab-config");
    expect(within(configTab).getByLabelText("Add tag")).toBeInTheDocument();
  });

  // AC3: Popover shows available tags with already-assigned disabled
  it("shows catalog tags in popover with assigned tags disabled", () => {
    renderSheet();
    const popover = screen.getByTestId("tag-popover-content");
    // bug and feature are already assigned
    const bugButton = within(popover).getByRole("button", { name: /bug/i });
    const featureButton = within(popover).getByRole("button", { name: /feature/i });
    const urgentButton = within(popover).getByRole("button", { name: /urgent/i });
    expect(bugButton).toBeDisabled();
    expect(featureButton).toBeDisabled();
    expect(urgentButton).not.toBeDisabled();
  });

  // AC3: Clicking an unassigned tag adds it
  it("calls updateTags with the new tag added when clicking an unassigned tag", async () => {
    renderSheet();
    const popover = screen.getByTestId("tag-popover-content");
    await user.click(within(popover).getByRole("button", { name: /urgent/i }));
    expect(mockUpdateTags).toHaveBeenCalledWith({
      taskId: "task1",
      tags: ["bug", "feature", "urgent"],
    });
  });

  // AC4: Tags section renders even when task has no tags
  it("renders Tags section with Add button when task has no tags", () => {
    renderSheet({ tags: undefined });
    const configTab = screen.getByTestId("tab-config");
    expect(within(configTab).getByText("Tags")).toBeInTheDocument();
    expect(within(configTab).getByLabelText("Add tag")).toBeInTheDocument();
  });

  // AC4: Empty catalog shows helpful message
  it("shows empty catalog message when no tags are defined", () => {
    const task = makeTask({ tags: undefined });
    mockUseQuery.mockImplementation((ref: string) => {
      if (String(ref).includes("getById")) return task;
      if (String(ref).includes("listByTask")) return [];
      if (String(ref).includes("getByTask")) return [];
      if (String(ref).includes("taskTags")) return [];
      return undefined;
    });
    render(<TaskDetailSheet taskId={"task1" as any} onClose={vi.fn()} />);
    expect(
      screen.getByText("No tags defined. Open the Tags panel to create some.")
    ).toBeInTheDocument();
  });

  // AC5: Tag chip uses color from catalog
  it("applies tag color classes from the catalog", () => {
    renderSheet();
    const configTab = screen.getByTestId("tab-config");
    // "bug" has color "red" => bg-red-100, text-red-700
    // Use the remove button to locate the chip (unique to chips, not popover)
    const bugChip = within(configTab).getByLabelText("Remove tag bug").closest("span");
    expect(bugChip?.className).toContain("bg-red-100");
    expect(bugChip?.className).toContain("text-red-700");
  });

  // AC5: Legacy tag without catalog entry gets default muted style
  it("applies default muted style for tags not in catalog", () => {
    renderSheet({ tags: ["legacy-tag"] });
    const configTab = screen.getByTestId("tab-config");
    const chip = within(configTab).getByText("legacy-tag").closest("span");
    expect(chip?.className).toContain("bg-muted");
    expect(chip?.className).toContain("text-muted-foreground");
  });
});

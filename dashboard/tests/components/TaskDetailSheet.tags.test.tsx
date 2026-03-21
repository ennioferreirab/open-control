import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { testId } from "@/tests/helpers/mockConvex";
import type { Id } from "@/convex/_generated/dataModel";

// Stub scrollIntoView for jsdom (used by TaskDetailThreadTab on mount)
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const user = userEvent.setup({ delay: null });

// Mock convex/react hooks

vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    tasks: {
      getDetailView: "tasks:getDetailView",
      searchMergeCandidates: "tasks:searchMergeCandidates",
      approve: "tasks:approve",
      approveAndKickOff: "tasks:approveAndKickOff",
      pauseTask: "tasks:pauseTask",
      resumeTask: "tasks:resumeTask",
      retry: "tasks:retry",
      softDelete: "tasks:softDelete",
      updateTags: "tasks:updateTags",
      updateTitle: "tasks:updateTitle",
      updateDescription: "tasks:updateDescription",
      addTaskFiles: "tasks:addTaskFiles",
      removeTaskFile: "tasks:removeTaskFile",
    },
    messages: {
      postUserPlanMessage: "messages:postUserPlanMessage",
    },
    activities: { create: "activities:create" },
    tagAttributeValues: {
      removeByTaskAndTag: "tagAttributeValues:removeByTaskAndTag",
    },
    executionQuestions: {
      getPendingForTask: "executionQuestions:getPendingForTask",
    },
    agents: {
      getByName: "agents:getByName",
    },
    boards: {
      getById: "boards:getById",
    },
    interactiveSessions: {
      listSessions: "interactiveSessions:listSessions",
    },
    sessionActivityLog: {
      listForSession: "sessionActivityLog:listForSession",
    },
    skills: {
      getByName: "skills:getByName",
    },
    squadSpecs: {
      getAgentsSquadMemberships: "squadSpecs:getAgentsSquadMemberships",
    },
  },
}));

// Mock interactive session hooks — not relevant to tag editing
vi.mock("../../features/interactive/hooks/useTaskInteractiveSession", () => ({
  useTaskInteractiveSession: () => ({
    activeStep: null,
    session: null,
    liveStepIds: new Set(),
    stateLabel: null,
    identityLabel: null,
  }),
}));

vi.mock("../../features/interactive/hooks/useProviderSession", () => ({
  useProviderSession: () => ({
    status: null,
    liveEvents: [],
  }),
}));

// Mock child components that are not relevant to tag editing
vi.mock("../../features/agents/components/AgentConfigSheet", () => ({
  AgentConfigSheet: () => null,
}));
vi.mock("../../features/agents/components/SquadDetailSheet", () => ({
  SquadDetailSheet: () => null,
}));
vi.mock("../../features/thread/components/ThreadMessage", () => ({
  ThreadMessage: () => null,
}));
vi.mock("../../features/tasks/components/ExecutionPlanTab", () => ({
  ExecutionPlanTab: () => null,
}));
vi.mock("../../components/InlineRejection", () => ({
  InlineRejection: () => null,
}));
vi.mock("../../components/DocumentViewerModal", () => ({
  DocumentViewerModal: () => null,
}));
vi.mock("../../features/thread/components/ThreadInput", () => ({
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
  function Popover({ children }: { children: React.ReactNode }) {
    return <>{children}</>;
  }
  const PopoverTrigger = React.forwardRef<
    HTMLButtonElement,
    { children: React.ReactNode; asChild?: boolean; [key: string]: unknown }
  >(function PopoverTrigger({ children, asChild, ...props }, ref) {
    if (asChild && React.isValidElement(children)) {
      // Pass props to child without forwarding the ref to avoid render-time ref access
      return React.cloneElement(children as React.ReactElement<Record<string, unknown>>, {
        ...props,
      });
    }
    return (
      <button {...(props as React.ButtonHTMLAttributes<HTMLButtonElement>)} ref={ref}>
        {children as React.ReactNode}
      </button>
    );
  });
  PopoverTrigger.displayName = "PopoverTrigger";
  function PopoverContent({ children }: { children: React.ReactNode }) {
    return <div data-testid="tag-popover-content">{children}</div>;
  }
  return { Popover, PopoverTrigger, PopoverContent };
});

// Mock Sheet components
vi.mock("@/components/ui/sheet", () => {
  function Sheet({ children, open }: { children: React.ReactNode; open?: boolean }) {
    return open ? <div data-testid="sheet">{children}</div> : null;
  }
  function SheetContent({ children }: { children: React.ReactNode }) {
    return <div>{children}</div>;
  }
  function SheetHeader({ children }: { children: React.ReactNode }) {
    return <div>{children}</div>;
  }
  function SheetTitle({ children }: { children: React.ReactNode }) {
    return <div>{children}</div>;
  }
  function SheetDescription({
    children,
    asChild,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) {
    return asChild ? <>{children}</> : <div>{children}</div>;
  }
  return { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription };
});

vi.mock("@/components/ui/tabs", () => {
  function Tabs({
    children,
    value,
  }: {
    children: React.ReactNode;
    value?: string;
    onValueChange?: (v: string) => void;
  }) {
    return (
      <div data-testid="tabs" data-value={value}>
        {children}
      </div>
    );
  }
  function TabsList({ children }: { children: React.ReactNode }) {
    return <div>{children}</div>;
  }
  function TabsTrigger({ children, value }: { children: React.ReactNode; value?: string }) {
    return <button data-value={value}>{children}</button>;
  }
  function TabsContent({ children, value }: { children: React.ReactNode; value?: string }) {
    return <div data-testid={`tab-${value}`}>{children}</div>;
  }
  return { Tabs, TabsList, TabsTrigger, TabsContent };
});

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children, ...props }: { children: React.ReactNode; [key: string]: unknown }) => (
    <span {...(props as React.HTMLAttributes<HTMLSpanElement>)}>{children}</span>
  ),
}));
vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    ...props
  }: { children: React.ReactNode } & React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
}));
vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}));

// eslint-disable-next-line no-restricted-imports
import { useQuery, useMutation } from "convex/react";
import { TaskDetailSheet } from "../../features/tasks/components/TaskDetailSheet";

const mockUseQuery = useQuery as ReturnType<typeof vi.fn>;
const mockUseMutation = useMutation as ReturnType<typeof vi.fn>;

const SAMPLE_TAGS_CATALOG = [
  { _id: "t1", name: "bug", color: "red" },
  { _id: "t2", name: "feature", color: "blue" },
  { _id: "t3", name: "urgent", color: "amber" },
];

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    _id: testId<"tasks">("task1"),
    _creationTime: 1700000000000,
    title: "Test Task",
    status: "in_progress",
    assignedAgent: "dev-agent",
    trustLevel: "autonomous",
    tags: ["bug", "feature"],
    boardId: "board123" as Id<"boards">,
    createdAt: "2024-01-01T00:00:00.000Z",
    updatedAt: "2024-01-01T00:00:00.000Z",
    ...overrides,
  };
}

const SAMPLE_TAG_ATTRIBUTES = [
  {
    _id: "attr1",
    name: "priority",
    type: "select",
    options: ["high", "medium", "low"],
    createdAt: "2024-01-01",
  },
  { _id: "attr2", name: "severity", type: "text", createdAt: "2024-01-01" },
];

type TagAttributeValue = { tagName: string; attributeId: string; value: string };

function makeDetailView(
  task: ReturnType<typeof makeTask>,
  tagCatalog = SAMPLE_TAGS_CATALOG,
  tagAttributes: (typeof SAMPLE_TAG_ATTRIBUTES)[number][] = [],
  tagAttributeValues: TagAttributeValue[] = [],
) {
  return {
    task,
    board: null,
    messages: [],
    steps: [],
    files: [],
    tags: (task.tags as string[] | undefined) ?? [],
    tagCatalog,
    tagAttributes,
    tagAttributeValues,
    uiFlags: {
      isAwaitingKickoff: false,
      isPaused: task.status === "review",
      isManual: false,
      isPlanEditable: true,
    },
    allowedActions: {
      approve: task.status === "review",
      kickoff: task.status === "review" || task.status === "ready",
      pause: task.status === "in_progress",
      resume: task.status === "review",
      retry: task.status === "crashed" || task.status === "failed",
      savePlan: true,
      startInbox: task.status === "inbox",
      sendMessage: true,
    },
  };
}

describe("TaskDetailSheet — tag editing (Story 9-3)", () => {
  const mockUpdateTags = vi.fn();
  const noop = vi.fn().mockResolvedValue(undefined);

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
      if (String(ref).includes("getDetailView")) return makeDetailView(task);
      return undefined;
    });
    render(<TaskDetailSheet taskId={testId<"tasks">("task1")} onClose={vi.fn()} />);
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
      if (String(ref).includes("getDetailView")) return makeDetailView(task, []);
      return undefined;
    });
    render(<TaskDetailSheet taskId={testId<"tasks">("task1")} onClose={vi.fn()} />);
    expect(
      screen.getByText("No tags defined. Open the Tags panel to create some."),
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

describe("TaskDetailSheet — header tag chips", () => {
  const noop = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    noop.mockResolvedValue(undefined);
    mockUseMutation.mockReturnValue(noop);
  });

  function renderWithAttrs(
    taskOverrides: Record<string, unknown> = {},
    tagAttributes: (typeof SAMPLE_TAG_ATTRIBUTES)[number][] = [],
    tagAttributeValues: TagAttributeValue[] = [],
  ) {
    const task = makeTask(taskOverrides);
    mockUseQuery.mockImplementation((ref: string) => {
      if (String(ref).includes("getDetailView"))
        return makeDetailView(task, SAMPLE_TAGS_CATALOG, tagAttributes, tagAttributeValues);
      return undefined;
    });
    render(<TaskDetailSheet taskId={testId<"tasks">("task1")} onClose={vi.fn()} />);
    return task;
  }

  it("shows tag name next to status badge when no attribute values exist", () => {
    renderWithAttrs({ tags: ["bug"] });
    // The header area (outside tabs) should contain the tag chip
    const allBugTexts = screen.getAllByText("bug");
    // At least one should be outside the config tab (in the header)
    const headerChip = allBugTexts.find((el) => !el.closest("[data-testid='tab-config']"));
    expect(headerChip).toBeTruthy();
  });

  it("shows tag:attr=value format when attribute values exist", () => {
    renderWithAttrs({ tags: ["bug"] }, SAMPLE_TAG_ATTRIBUTES, [
      { tagName: "bug", attributeId: "attr1", value: "high" },
    ]);
    const chip = screen.getByText("bug:priority=high");
    expect(chip).toBeInTheDocument();
  });

  it("uses tag color from catalog for header chips", () => {
    renderWithAttrs({ tags: ["bug"] });
    const allBugTexts = screen.getAllByText("bug");
    // The text is inside <span class="truncate"> inside <span class="chipClass">
    // Go up to the outer chip span (parent of the truncate span)
    const headerText = allBugTexts.find((el) => !el.closest("[data-testid='tab-config']"));
    const chipSpan = headerText?.parentElement;
    expect(chipSpan?.className).toContain("bg-red-100");
    expect(chipSpan?.className).toContain("text-red-700");
  });

  it("applies muted style for tags not in catalog", () => {
    renderWithAttrs({ tags: ["unknown-tag"] });
    const allTexts = screen.getAllByText("unknown-tag");
    const headerText = allTexts.find((el) => !el.closest("[data-testid='tab-config']"));
    const chipSpan = headerText?.parentElement;
    expect(chipSpan?.className).toContain("bg-muted");
  });

  it("does not render header chips when task has no tags", () => {
    renderWithAttrs({ tags: [] });
    // Status badge should still be there
    expect(screen.getByText("in progress")).toBeInTheDocument();
  });
});

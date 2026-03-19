import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { AgentConfigSheet } from "@/features/agents/components/AgentConfigSheet";
import type { AgentConfigSheetData } from "@/features/agents/hooks/useAgentConfigSheetData";
import type { Doc } from "@/convex/_generated/dataModel";

// Mock agent data
const mockAgent: Doc<"agents"> = {
  _id: "agent1" as never,
  _creationTime: 1000,
  name: "test-agent",
  displayName: "Test Agent",
  role: "Developer",
  prompt: "You are a developer.",
  skills: ["github", "memory"],
  model: "claude-sonnet-4-6",
  status: "active",
  enabled: true as boolean | undefined,
  lastActiveAt: "2025-01-01T00:00:00Z",
};

let mockQueryResult: typeof mockAgent | null | undefined = mockAgent;
const mockUpdateConfig = vi.fn();
const mockSetEnabled = vi.fn();

let hookOverrides: Partial<AgentConfigSheetData> = {};

const defaultHookData: AgentConfigSheetData = {
  agent: mockAgent,
  updateConfig: mockUpdateConfig,
  setEnabled: mockSetEnabled,
  connectedModels: ["claude-sonnet-4-6"],
  modelTiers: {
    low: "claude-haiku-4-5",
    medium: "claude-sonnet-4-6",
    high: "claude-opus-4-6",
  },
};

vi.mock("@/features/agents/hooks/useActiveSquadsForAgent", () => ({
  useActiveSquadsForAgent: () => [],
}));

vi.mock("@/features/agents/hooks/useAgentConfigSheetData", () => ({
  useAgentConfigSheetData: (agentName: string | null) => {
    if (!agentName) {
      return { ...defaultHookData, agent: undefined, ...hookOverrides };
    }
    return {
      ...defaultHookData,
      agent: mockQueryResult,
      ...hookOverrides,
    };
  },
}));

// Mock SkillsSelector to keep tests focused
vi.mock("@/components/SkillsSelector", () => ({
  SkillsSelector: ({
    selected,
    onChange,
  }: {
    selected: string[];
    onChange: (s: string[]) => void;
  }) => (
    <div data-testid="skills-selector" data-selected={selected.join(",")}>
      <button onClick={() => onChange([...selected, "new-skill"])}>Add Skill</button>
    </div>
  ),
}));

// Mock AgentSidebarItem exports
vi.mock("@/features/agents/components/AgentSidebarItem", () => ({
  getAvatarColor: () => "bg-blue-500",
  getInitials: (name: string) => name.slice(0, 2).toUpperCase(),
}));

vi.mock("@/components/PromptEditModal", () => ({
  PromptEditModal: () => null,
}));

vi.mock("@/components/AgentTextViewerModal", () => ({
  AgentTextViewerModal: () => null,
}));

vi.mock("@/features/agents/components/SkillDetailDialog", () => ({
  SkillDetailDialog: () => null,
}));

// Mock ShadCN UI components
vi.mock("@/components/ui/sheet", () => ({
  Sheet: ({ children, open }: React.PropsWithChildren<{ open: boolean }>) =>
    open ? <div data-testid="sheet">{children}</div> : null,
  SheetContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SheetHeader: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SheetTitle: ({ children }: React.PropsWithChildren) => <h2>{children}</h2>,
  SheetDescription: ({ children, asChild }: React.PropsWithChildren<{ asChild?: boolean }>) => {
    void asChild;
    return <div>{children}</div>;
  },
}));

vi.mock("@/components/ui/alert-dialog", () => ({
  AlertDialog: ({ children, open }: React.PropsWithChildren<{ open: boolean }>) =>
    open ? <div data-testid="alert-dialog">{children}</div> : null,
  AlertDialogContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  AlertDialogHeader: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: React.PropsWithChildren) => <h3>{children}</h3>,
  AlertDialogDescription: ({ children }: React.PropsWithChildren) => <p>{children}</p>,
  AlertDialogFooter: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  AlertDialogCancel: ({ children }: React.PropsWithChildren) => <button>{children}</button>,
  AlertDialogAction: ({ children, onClick }: React.PropsWithChildren<{ onClick?: () => void }>) => (
    <button onClick={onClick}>{children}</button>
  ),
}));

vi.mock("@/components/ui/input", () => ({
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock("@/components/ui/textarea", () => ({
  Textarea: (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...props} />,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    ...props
  }: React.PropsWithChildren<React.ButtonHTMLAttributes<HTMLButtonElement>>) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}));

vi.mock("@/components/ui/switch", () => ({
  Switch: ({
    id,
    checked,
    onCheckedChange,
  }: {
    id?: string;
    checked?: boolean;
    onCheckedChange?: (v: boolean) => void;
  }) => (
    <button
      data-testid="enabled-switch"
      data-state={checked ? "checked" : "unchecked"}
      role="switch"
      aria-checked={checked}
      id={id}
      onClick={() => onCheckedChange?.(!checked)}
    >
      {checked ? "on" : "off"}
    </button>
  ),
}));

describe("AgentConfigSheet", () => {
  async function renderLoadedSheet(overrides?: {
    agentName?: string | null;
    onClose?: () => void;
  }) {
    render(
      <AgentConfigSheet
        agentName={overrides?.agentName ?? "test-agent"}
        onClose={overrides?.onClose ?? vi.fn()}
      />,
    );

    if (!overrides || overrides.agentName !== null) {
      await screen.findByDisplayValue("Developer");
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith("/api/agents/test-agent/memory/MEMORY.md");
        expect(fetch).toHaveBeenCalledWith("/api/agents/test-agent/memory/HISTORY.md");
      });
      await waitFor(() => {
        expect(screen.queryAllByText("Loading...")).toHaveLength(0);
      });
    }
  }

  beforeEach(() => {
    mockQueryResult = mockAgent;
    hookOverrides = {};
    mockUpdateConfig.mockReset();
    mockUpdateConfig.mockResolvedValue(undefined);
    mockSetEnabled.mockReset();
    mockSetEnabled.mockResolvedValue(undefined);
    // Mock fetch for memory/history endpoints (return 404 by default)
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
  });

  afterEach(() => {
    cleanup();
  });

  it("renders nothing when agentName is null", () => {
    const { container } = render(<AgentConfigSheet agentName={null} onClose={vi.fn()} />);
    expect(screen.queryByTestId("sheet")).not.toBeInTheDocument();
    void container;
  });

  it("shows Save button disabled when no changes", async () => {
    await renderLoadedSheet();

    const saveButton = screen.getByText("Save");
    expect(saveButton).toBeDisabled();
  });

  it("enables Save button when form is dirty", async () => {
    await renderLoadedSheet();

    const roleInput = screen.getByDisplayValue("Developer");
    fireEvent.change(roleInput, { target: { value: "Senior Developer" } });

    const saveButton = screen.getByText("Save");
    expect(saveButton).not.toBeDisabled();
  });

  it("shows validation error for empty role on blur", async () => {
    await renderLoadedSheet();

    const roleInput = screen.getByDisplayValue("Developer");
    fireEvent.change(roleInput, { target: { value: "" } });
    fireEvent.blur(roleInput);

    expect(screen.getByText("Agent role cannot be empty.")).toBeInTheDocument();
  });

  it("shows validation error for empty prompt on blur", async () => {
    await renderLoadedSheet();

    const promptInput = screen.getByDisplayValue("You are a developer.");
    fireEvent.change(promptInput, { target: { value: "" } });
    fireEvent.blur(promptInput);

    expect(screen.getByText("Agent prompt cannot be empty.")).toBeInTheDocument();
  });

  it("calls updateConfig mutation on save", async () => {
    await renderLoadedSheet();

    const roleInput = screen.getByDisplayValue("Developer");
    fireEvent.change(roleInput, { target: { value: "Senior Developer" } });

    const saveButton = screen.getByText("Save");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockUpdateConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "test-agent",
          role: "Senior Developer",
        }),
      );
    });
  });

  it("shows success checkmark after save", async () => {
    await renderLoadedSheet();

    const roleInput = screen.getByDisplayValue("Developer");
    fireEvent.change(roleInput, { target: { value: "Senior Developer" } });

    const saveButton = screen.getByText("Save");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("Saved")).toBeInTheDocument();
    });
  });

  it("shows error banner when save fails", async () => {
    mockUpdateConfig.mockRejectedValue(new Error("Network error"));

    await renderLoadedSheet();

    const roleInput = screen.getByDisplayValue("Developer");
    fireEvent.change(roleInput, { target: { value: "Senior Developer" } });

    const saveButton = screen.getByText("Save");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("Failed to save. Please try again.")).toBeInTheDocument();
    });
  });

  // --- Enable/disable toggle tests ---

  it("renders Deactivated label and unchecked switch when agent is disabled", async () => {
    mockQueryResult = { ...mockAgent, enabled: false };
    await renderLoadedSheet();

    const deactivatedTexts = screen.getAllByText("Deactivated");
    // Should appear in both header status and toggle label
    expect(deactivatedTexts.length).toBeGreaterThanOrEqual(2);
    const toggle = screen.getByTestId("enabled-switch");
    expect(toggle.getAttribute("data-state")).toBe("unchecked");
  });

  it("does not call setEnabled immediately when toggle is clicked", async () => {
    await renderLoadedSheet();

    const toggle = screen.getByTestId("enabled-switch");
    fireEvent.click(toggle);

    // Toggle only updates local state -- mutation fires on Save
    expect(mockSetEnabled).not.toHaveBeenCalled();
  });

  it("enables Save button when toggle is changed (form becomes dirty)", async () => {
    await renderLoadedSheet();

    const saveButton = screen.getByText("Save");
    expect(saveButton).toBeDisabled();

    const toggle = screen.getByTestId("enabled-switch");
    fireEvent.click(toggle);

    expect(saveButton).not.toBeDisabled();
  });

  it("calls setEnabled on Save when enabled state changed", async () => {
    await renderLoadedSheet();

    const toggle = screen.getByTestId("enabled-switch");
    fireEvent.click(toggle);

    const saveButton = screen.getByText("Save");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockSetEnabled).toHaveBeenCalledWith({
        agentName: "test-agent",
        enabled: false,
      });
    });
  });

  it("calls setEnabled with true on Save when re-enabling a disabled agent", async () => {
    mockQueryResult = { ...mockAgent, enabled: false };
    await renderLoadedSheet();

    const toggle = screen.getByTestId("enabled-switch");
    fireEvent.click(toggle);

    const saveButton = screen.getByText("Save");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockSetEnabled).toHaveBeenCalledWith({
        agentName: "test-agent",
        enabled: true,
      });
    });
  });

  it("shows info text when agent is disabled", async () => {
    mockQueryResult = { ...mockAgent, enabled: false };
    await renderLoadedSheet();

    expect(screen.getByText("This agent will not receive new tasks")).toBeInTheDocument();
  });

  it("shows info text when toggle is switched to disabled (before save)", async () => {
    await renderLoadedSheet();

    expect(screen.queryByText("This agent will not receive new tasks")).not.toBeInTheDocument();

    const toggle = screen.getByTestId("enabled-switch");
    fireEvent.click(toggle);

    expect(screen.getByText("This agent will not receive new tasks")).toBeInTheDocument();
  });

  it("does not show info text when agent is enabled", async () => {
    await renderLoadedSheet();

    expect(screen.queryByText("This agent will not receive new tasks")).not.toBeInTheDocument();
  });

  // --- Memory/History section tests ---

  it("shows 'No memory yet.' placeholder when fetch returns 404", async () => {
    await renderLoadedSheet();

    await waitFor(() => {
      expect(screen.getByText("No memory yet.")).toBeInTheDocument();
    });
  });

  it("shows 'No history yet.' placeholder when fetch returns 404", async () => {
    await renderLoadedSheet();

    await waitFor(() => {
      expect(screen.getByText("No history yet.")).toBeInTheDocument();
    });
  });

  it("fetches memory and history when agentName is set", async () => {
    await renderLoadedSheet();

    expect(fetch).toHaveBeenCalledWith("/api/agents/test-agent/memory/MEMORY.md");
    expect(fetch).toHaveBeenCalledWith("/api/agents/test-agent/memory/HISTORY.md");
  });

  it("shows memory content and Edit button when fetch succeeds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          url.includes("MEMORY.md")
            ? { ok: true, text: () => Promise.resolve("Agent Memory Content") }
            : { ok: false, status: 404 },
        ),
      ),
    );

    await renderLoadedSheet();

    await waitFor(() => {
      expect(screen.getByText("Agent Memory Content")).toBeInTheDocument();
    });

    // Edit button should appear for Memory and History
    const editButtons = screen.getAllByText("Edit");
    expect(editButtons.length).toBeGreaterThanOrEqual(1);
  });
});

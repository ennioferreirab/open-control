import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockUpdateConfig = vi.fn();
const mockSetEnabled = vi.fn();

vi.mock("@/features/agents/hooks/useAgentConfigSheetData", () => ({
  useAgentConfigSheetData: vi.fn(),
}));

vi.mock("@/features/agents/hooks/useActiveSquadsForAgent", () => ({
  useActiveSquadsForAgent: () => [],
}));

vi.mock("@/features/agents/components/AgentSidebarItem", () => ({
  getAvatarColor: () => "bg-blue-500",
  getInitials: () => "DA",
}));

vi.mock("@/components/SkillsSelector", () => ({
  SkillsSelector: () => <div data-testid="skills-selector" />,
}));

vi.mock("@/components/PromptEditModal", () => ({
  PromptEditModal: () => null,
}));

vi.mock("@/features/agents/components/SkillDetailDialog", () => ({
  SkillDetailDialog: () => null,
}));

vi.mock("@/components/AgentTextViewerModal", () => ({
  AgentTextViewerModal: ({
    open,
    title,
    content,
    onClose,
    onSave,
  }: {
    open: boolean;
    title: string;
    content: string;
    onClose: () => void;
    onSave?: (content: string) => Promise<void> | void;
  }) => {
    const [draft, setDraft] = React.useState(content);

    React.useEffect(() => {
      if (open) setDraft(content);
    }, [open, content]);

    if (!open) return null;

    return (
      <div>
        <p>{title}</p>
        <textarea
          aria-label={`${title} content`}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="button" onClick={onClose}>
          Cancel {title}
        </button>
        <button
          type="button"
          onClick={async () => {
            await onSave?.(draft);
            onClose();
          }}
        >
          Save {title}
        </button>
      </div>
    );
  },
}));

vi.mock("@/components/ui/sheet", () => ({
  Sheet: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SheetContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SheetHeader: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SheetTitle: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  SheetDescription: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
}));

vi.mock("@/components/ui/alert-dialog", () => ({
  AlertDialog: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  AlertDialogAction: ({ children, onClick }: React.PropsWithChildren<{ onClick?: () => void }>) => (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  ),
  AlertDialogCancel: ({ children }: React.PropsWithChildren) => (
    <button type="button">{children}</button>
  ),
  AlertDialogContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  AlertDialogDescription: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  AlertDialogFooter: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  AlertDialogHeader: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
}));

vi.mock("@/components/ui/input", () => ({
  Input: ({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) => (
    <input className={className} {...props} />
  ),
}));

vi.mock("@/components/ui/textarea", () => ({
  Textarea: ({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
    <textarea className={className} {...props} />
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    type = "button",
    ...props
  }: React.PropsWithChildren<
    React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: string; size?: string }
  >) => (
    <button type={type} onClick={onClick} disabled={disabled} {...props}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}));

vi.mock("@/components/ui/switch", () => ({
  Switch: ({
    checked,
    onCheckedChange,
    disabled,
    id,
  }: {
    checked: boolean;
    onCheckedChange?: (checked: boolean) => void;
    disabled?: boolean;
    id?: string;
  }) => (
    <input
      id={id}
      type="checkbox"
      checked={checked}
      disabled={disabled}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
    />
  ),
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
}));

vi.mock("@/components/ui/tooltip", () => ({
  TooltipProvider: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  Tooltip: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  TooltipTrigger: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  TooltipContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
}));

vi.mock("@/components/ui/select", async () => {
  const ReactModule = await import("react");

  type Option = { value: string; label: React.ReactNode; disabled?: boolean };

  const SelectItem = ({
    children,
  }: React.PropsWithChildren<{ value: string; disabled?: boolean }>) => <>{children}</>;
  (SelectItem as { __mockSelectItem?: boolean }).__mockSelectItem = true;

  function extractOptions(children: React.ReactNode): Option[] {
    const options: Option[] = [];

    ReactModule.Children.forEach(children, (child) => {
      if (!ReactModule.isValidElement(child)) return;

      const childType = child.type as { __mockSelectItem?: boolean };
      if (childType.__mockSelectItem) {
        const typedChild = child as React.ReactElement<{
          value: string;
          children: React.ReactNode;
          disabled?: boolean;
        }>;
        options.push({
          value: typedChild.props.value,
          label: typedChild.props.children,
          disabled: typedChild.props.disabled,
        });
        return;
      }

      const withChildren = child as React.ReactElement<{ children?: React.ReactNode }>;
      if (withChildren.props?.children) {
        options.push(...extractOptions(withChildren.props.children));
      }
    });

    return options;
  }

  return {
    Select: ({
      value,
      onValueChange,
      children,
    }: React.PropsWithChildren<{ value?: string; onValueChange?: (value: string) => void }>) => {
      const options = extractOptions(children);

      return (
        <select value={value} onChange={(e) => onValueChange?.(e.target.value)}>
          {options.map((option) => (
            <option key={option.value} value={option.value} disabled={option.disabled}>
              {option.label}
            </option>
          ))}
        </select>
      );
    },
    SelectContent: ({ children }: React.PropsWithChildren) => <>{children}</>,
    SelectItem,
    SelectTrigger: ({ children }: React.PropsWithChildren) => <>{children}</>,
    SelectValue: ({ children }: React.PropsWithChildren<{ placeholder?: string }>) => (
      <>{children}</>
    ),
    SelectGroup: ({ children }: React.PropsWithChildren) => <>{children}</>,
    SelectLabel: ({ children }: React.PropsWithChildren) => <>{children}</>,
    SelectSeparator: () => null,
  };
});

import { useAgentConfigSheetData } from "@/features/agents/hooks/useAgentConfigSheetData";
import { AgentConfigSheet } from "./AgentConfigSheet";

const mockedUseAgentConfigSheetData = vi.mocked(useAgentConfigSheetData);

describe("AgentConfigSheet", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const baseAgent = {
      _id: "agent1",
      _creationTime: 0,
      name: "designer-agent",
      displayName: "Designer Agent",
      role: "Product designer",
      prompt: "Design polished interfaces",
      soul: "Balance craft, clarity, and systems thinking.",
      skills: ["design"],
      model: "claude-sonnet-4-6",
      status: "idle",
      enabled: true,
      variables: [],
    };

    mockedUseAgentConfigSheetData.mockImplementation(() => ({
      agent: {
        ...baseAgent,
        skills: [...baseAgent.skills],
        variables: [...baseAgent.variables],
      } as never,
      updateConfig: mockUpdateConfig.mockResolvedValue(undefined),
      setEnabled: mockSetEnabled.mockResolvedValue(undefined),
      connectedModels: ["claude-sonnet-4-6", "claude-opus-4-6"],
      modelTiers: { "standard-low": "claude-haiku-4-5" },
    }));

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);

        if (!init || init.method === undefined) {
          return Promise.resolve({
            ok: false,
            text: async () => "",
          });
        }

        if (url.includes("/config") && init.method === "PUT") {
          return Promise.resolve({
            ok: true,
            text: async () => "",
          });
        }

        return Promise.resolve({
          ok: true,
          text: async () => "",
        });
      }),
    );
  });

  it("renders a Soul section with preview text", async () => {
    render(<AgentConfigSheet agentName="designer-agent" onClose={vi.fn()} />);

    expect(await screen.findByText("Soul")).toBeInTheDocument();
    expect(screen.getByText(/Balance craft, clarity, and systems thinking/)).toBeInTheDocument();
  });

  it("enables Save after editing the prompt", async () => {
    const user = userEvent.setup();
    render(<AgentConfigSheet agentName="designer-agent" onClose={vi.fn()} />);

    const saveButton = screen.getByRole("button", { name: /^save$/i });
    expect(saveButton).toBeDisabled();

    await user.type(screen.getByLabelText("Prompt"), " with stronger system rationale");

    expect(saveButton).toBeEnabled();
  });

  it("enables Save after changing the configured model", async () => {
    const user = userEvent.setup();
    render(<AgentConfigSheet agentName="designer-agent" onClose={vi.fn()} />);

    const saveButton = screen.getByRole("button", { name: /^save$/i });
    expect(saveButton).toBeDisabled();

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[2], "claude-opus-4-6");

    expect(saveButton).toBeEnabled();
  });

  it("persists soul in Convex and YAML when saved", async () => {
    const user = userEvent.setup();
    render(<AgentConfigSheet agentName="designer-agent" onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /edit soul/i }));
    await user.clear(screen.getByLabelText("Soul content"));
    await user.type(
      screen.getByLabelText("Soul content"),
      "Push the visual system while protecting usability.",
    );
    await user.click(screen.getByRole("button", { name: /save soul/i }));

    const saveButton = screen.getByRole("button", { name: /^save$/i });
    expect(saveButton).toBeEnabled();

    await user.click(saveButton);

    await waitFor(() => {
      expect(mockUpdateConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "designer-agent",
          soul: "Push the visual system while protecting usability.",
        }),
      );
    });

    const fetchCalls = vi
      .mocked(fetch)
      .mock.calls.filter(
        ([url, init]) => String(url).includes("/config") && init?.method === "PUT",
      );
    expect(fetchCalls).toHaveLength(1);

    const [, init] = fetchCalls[0];
    expect(JSON.parse(String(init?.body))).toEqual(
      expect.objectContaining({
        soul: "Push the visual system while protecting usability.",
      }),
    );
  });
});

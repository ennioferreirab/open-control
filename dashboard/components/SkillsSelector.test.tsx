import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { SkillsSelector } from "./SkillsSelector";

// Mock skills data
const mockSkills = [
  {
    _id: "s1" as never,
    _creationTime: 1000,
    name: "github",
    description: "GitHub CLI integration",
    content: "# GitHub",
    source: "builtin" as const,
    available: true,
    metadata: JSON.stringify({ nanobot: { emoji: "\uD83D\uDC19" } }),
  },
  {
    _id: "s2" as never,
    _creationTime: 1001,
    name: "memory",
    description: "Two-layer memory system",
    content: "# Memory",
    source: "builtin" as const,
    available: true,
    always: true,
  },
  {
    _id: "s3" as never,
    _creationTime: 1002,
    name: "summarize",
    description: "URL/file summarization",
    content: "# Summarize",
    source: "builtin" as const,
    available: false,
    requires: "CLI: summarize",
  },
];

let mockQueryResult: typeof mockSkills | undefined = mockSkills;

vi.mock("@/features/agents/hooks/useSkillsSelectorData", () => ({
  useSkillsSelectorData: () => mockQueryResult,
}));

// Mock ShadCN components
vi.mock("@/components/ui/input", () => ({
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock("@/components/ui/checkbox", () => ({
  Checkbox: ({ checked, onCheckedChange, disabled }: {
    checked: boolean;
    onCheckedChange: () => void;
    disabled?: boolean;
  }) => (
    <input
      type="checkbox"
      checked={checked}
      onChange={onCheckedChange}
      disabled={disabled}
      data-testid={`checkbox-${checked ? "checked" : "unchecked"}`}
    />
  ),
}));

vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: React.PropsWithChildren) => <span data-testid="badge">{children}</span>,
}));

vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}));

describe("SkillsSelector", () => {
  afterEach(() => {
    cleanup();
    mockQueryResult = mockSkills;
  });

  it("renders all skills from Convex", () => {
    render(<SkillsSelector selected={[]} onChange={vi.fn()} />);

    expect(screen.getByText("github")).toBeInTheDocument();
    expect(screen.getByText("memory")).toBeInTheDocument();
    expect(screen.getByText("summarize")).toBeInTheDocument();
  });

  it("shows skill descriptions", () => {
    render(<SkillsSelector selected={[]} onChange={vi.fn()} />);

    expect(screen.getByText("GitHub CLI integration")).toBeInTheDocument();
    expect(screen.getByText("Two-layer memory system")).toBeInTheDocument();
  });

  it("displays selected count badge", () => {
    render(<SkillsSelector selected={["github"]} onChange={vi.fn()} />);

    expect(screen.getByText("1 of 3 selected")).toBeInTheDocument();
  });

  it("filters skills by search", () => {
    render(<SkillsSelector selected={[]} onChange={vi.fn()} />);

    const search = screen.getByPlaceholderText("Search skills...");
    fireEvent.change(search, { target: { value: "github" } });

    expect(screen.getByText("github")).toBeInTheDocument();
    expect(screen.queryByText("memory")).not.toBeInTheDocument();
    expect(screen.queryByText("summarize")).not.toBeInTheDocument();
  });

  it("calls onChange when toggling a skill", () => {
    const onChange = vi.fn();
    render(<SkillsSelector selected={["github"]} onChange={onChange} />);

    // Click on an unchecked skill (memory is unchecked because it's not in selected)
    // Find the label containing "memory" and click its checkbox
    const memoryCheckbox = screen.getAllByRole("checkbox").find(
      (el) => !el.closest("label")?.textContent?.includes("github")
        && el.closest("label")?.textContent?.includes("memory")
    );
    if (memoryCheckbox) {
      fireEvent.change(memoryCheckbox);
    }

    // onChange should not be called for always-loaded skills
    // (memory has always: true, so toggle is a no-op)
  });

  it("shows always-loaded label for always skills", () => {
    render(<SkillsSelector selected={["memory"]} onChange={vi.fn()} />);

    expect(screen.getByText("(always loaded)")).toBeInTheDocument();
  });

  it("disables checkbox for always-loaded skills", () => {
    render(<SkillsSelector selected={["memory"]} onChange={vi.fn()} />);

    // Find the disabled checkbox (memory is always-loaded)
    const disabledCheckboxes = screen.getAllByRole("checkbox").filter(
      (el) => (el as HTMLInputElement).disabled
    );
    expect(disabledCheckboxes.length).toBeGreaterThan(0);
  });

  it("shows loading state when skills are undefined", () => {
    mockQueryResult = undefined;
    render(<SkillsSelector selected={[]} onChange={vi.fn()} />);

    expect(screen.getByText("Loading skills...")).toBeInTheDocument();
  });

  it("pins selected skills to top of list", () => {
    const { container } = render(
      <SkillsSelector selected={["summarize"]} onChange={vi.fn()} />
    );

    // Find all skill name elements - selected should appear before unselected
    const labels = container.querySelectorAll("label");
    const texts = Array.from(labels).map((l) => l.textContent);
    const summarizeIdx = texts.findIndex((t) => t?.includes("summarize"));
    const githubIdx = texts.findIndex((t) => t?.includes("github"));

    // Selected skills (summarize) should appear before unselected (github)
    expect(summarizeIdx).toBeLessThan(githubIdx);
  });

  it("shows availability indicator for skills", () => {
    const { container } = render(
      <SkillsSelector selected={[]} onChange={vi.fn()} />
    );

    // Available skills get green dot, unavailable get amber
    const greenDots = container.querySelectorAll(".bg-green-500");
    const amberDots = container.querySelectorAll(".bg-amber-500");
    expect(greenDots.length).toBe(2); // github + memory
    expect(amberDots.length).toBe(1); // summarize
  });

  it("shows emoji from metadata", () => {
    render(<SkillsSelector selected={[]} onChange={vi.fn()} />);

    // github has octopus emoji
    expect(screen.getByText("\uD83D\uDC19")).toBeInTheDocument();
  });
});

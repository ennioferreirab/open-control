import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const user = userEvent.setup({ delay: null });

vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    tasks: { create: "tasks:create" },
    agents: { list: "agents:list" },
    taskTags: { list: "taskTags:list" },
  },
}));

import { useQuery, useMutation } from "convex/react";
import { TaskInput } from "../../components/TaskInput";

const mockUseQuery = useQuery as ReturnType<typeof vi.fn>;
const mockUseMutation = useMutation as ReturnType<typeof vi.fn>;

/**
 * Helper: find the supervision mode button (Eye/Zap) by its title attribute.
 * We use title instead of aria-label because aria-hidden causes getByRole
 * to report the accessible name as empty.
 */
function getSupervisionButton(): HTMLElement {
  return screen.getByTitle(/^(Autonomous|Supervised) mode$/);
}

/** Helper: find the toggle options (ChevronDown) button by aria-label. */
function getToggleOptionsButton(): HTMLElement {
  return screen.getByLabelText("Toggle options");
}

describe("TaskInput — layout shift prevention (Story 8-1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseMutation.mockReturnValue(vi.fn().mockResolvedValue(undefined));
    mockUseQuery.mockReturnValue([]);
  });

  it("renders Eye/Zap button in DOM even when in manual mode (AC: 1)", async () => {
    render(<TaskInput />);

    // In AI mode (default), the supervision button is visible
    const supervisionBtn = getSupervisionButton();
    expect(supervisionBtn).toBeInTheDocument();
    expect(supervisionBtn).not.toHaveClass("opacity-0");

    // Switch to manual mode
    await user.click(screen.getByRole("button", { name: /Switch to manual mode/i }));

    // Button should still be in DOM but visually hidden
    const hiddenBtn = getSupervisionButton();
    expect(hiddenBtn).toBeInTheDocument();
    expect(hiddenBtn).toHaveClass("opacity-0");
    expect(hiddenBtn).toHaveClass("pointer-events-none");
  });

  it("renders ChevronDown toggle options button in DOM even when in manual mode (AC: 1)", async () => {
    render(<TaskInput />);

    // In AI mode (default), the toggle options button is visible
    const toggleBtn = getToggleOptionsButton();
    expect(toggleBtn).toBeInTheDocument();
    expect(toggleBtn).not.toHaveClass("opacity-0");

    // Switch to manual mode
    await user.click(screen.getByRole("button", { name: /Switch to manual mode/i }));

    // Button should still be in DOM but visually hidden
    const hiddenBtn = getToggleOptionsButton();
    expect(hiddenBtn).toBeInTheDocument();
    expect(hiddenBtn).toHaveClass("opacity-0");
    expect(hiddenBtn).toHaveClass("pointer-events-none");
  });

  it("sets tabIndex=-1 on hidden buttons so they are not keyboard-focusable (AC: 3)", async () => {
    render(<TaskInput />);

    // Switch to manual mode
    await user.click(screen.getByRole("button", { name: /Switch to manual mode/i }));

    expect(getSupervisionButton()).toHaveAttribute("tabindex", "-1");
    expect(getToggleOptionsButton()).toHaveAttribute("tabindex", "-1");
  });

  it("sets aria-hidden on hidden buttons for screen reader compliance (AC: 3)", async () => {
    render(<TaskInput />);

    // Switch to manual mode
    await user.click(screen.getByRole("button", { name: /Switch to manual mode/i }));

    expect(getSupervisionButton()).toHaveAttribute("aria-hidden", "true");
    expect(getToggleOptionsButton()).toHaveAttribute("aria-hidden", "true");
  });

  it("does NOT set aria-hidden or tabIndex=-1 when in AI mode", () => {
    render(<TaskInput />);

    const supervisionBtn = getSupervisionButton();
    const toggleBtn = getToggleOptionsButton();

    expect(supervisionBtn).not.toHaveAttribute("aria-hidden");
    expect(supervisionBtn).not.toHaveAttribute("tabindex", "-1");
    expect(toggleBtn).not.toHaveAttribute("aria-hidden");
    expect(toggleBtn).not.toHaveAttribute("tabindex", "-1");
  });

  it("restores button visibility when switching back to AI mode (AC: 1)", async () => {
    render(<TaskInput />);

    // Switch to manual
    await user.click(screen.getByRole("button", { name: /Switch to manual mode/i }));

    // Buttons are hidden
    expect(getSupervisionButton()).toHaveClass("opacity-0");

    // Switch back to AI
    await user.click(screen.getByRole("button", { name: /Switch to AI mode/i }));

    // Buttons should be visible again
    const supervisionBtn = getSupervisionButton();
    expect(supervisionBtn).not.toHaveClass("opacity-0");
    expect(supervisionBtn).not.toHaveAttribute("aria-hidden");

    const toggleBtn = getToggleOptionsButton();
    expect(toggleBtn).not.toHaveClass("opacity-0");
    expect(toggleBtn).not.toHaveAttribute("aria-hidden");
  });

  it("uses CSS transition classes for smooth opacity animation (AC: 2)", () => {
    render(<TaskInput />);

    const supervisionBtn = getSupervisionButton();
    const toggleBtn = getToggleOptionsButton();

    // Verify transition classes are present for smooth animation
    expect(supervisionBtn.className).toMatch(/transition/);
    expect(toggleBtn.className).toMatch(/transition/);
  });

  it("CollapsibleContent has Radix animation classes for smooth expand/collapse (AC: 4)", () => {
    render(<TaskInput />);

    // The CollapsibleContent is the element with data-state that also has our animation classes.
    // Radix Collapsible sets data-state on both root and content. We find the content one
    // by looking for the element with our specific animation class.
    const elements = document.querySelectorAll("[data-state]");
    const collapsibleContent = Array.from(elements).find((el) =>
      el.className.includes("animate-in")
    );
    expect(collapsibleContent).toBeTruthy();
    expect(collapsibleContent!.className).toContain("data-[state=open]:animate-in");
    expect(collapsibleContent!.className).toContain("data-[state=closed]:animate-out");
    expect(collapsibleContent!.className).toContain("overflow-hidden");
  });
});

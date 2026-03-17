import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock useTaskCardActions to avoid convex dependency
const mockToggleFavoriteTask = vi.fn();

vi.mock("@/features/tasks/hooks/useTaskCardActions", () => ({
  useTaskCardActions: () => ({
    approveTask: vi.fn(),
    approveAndKickOffTask: vi.fn(),
    softDeleteTask: vi.fn(),
    toggleFavoriteTask: mockToggleFavoriteTask,
  }),
}));

import { CompactFavoriteCard } from "../../components/CompactFavoriteCard";

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    _id: "task1" as any,
    _creationTime: 1700000000000,
    title: "Test Task Title",
    status: "in_progress",
    assignedAgent: "dev-agent",
    trustLevel: "autonomous",
    isFavorite: true,
    createdAt: "2024-01-01T00:00:00.000Z",
    updatedAt: "2024-01-01T00:00:00.000Z",
    ...overrides,
  } as any;
}

describe("CompactFavoriteCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockToggleFavoriteTask.mockResolvedValue(undefined);
  });

  it("renders task title", () => {
    render(<CompactFavoriteCard task={makeTask()} />);
    expect(screen.getByText("Test Task Title")).toBeInTheDocument();
  });

  it("renders agent initials from assignedAgent", () => {
    render(<CompactFavoriteCard task={makeTask({ assignedAgent: "dev-agent" })} />);
    expect(screen.getByText("DA")).toBeInTheDocument();
  });

  it("renders '?' when no agent assigned", () => {
    render(<CompactFavoriteCard task={makeTask({ assignedAgent: undefined })} />);
    expect(screen.getByText("?")).toBeInTheDocument();
  });

  it("renders status badge with formatted status", () => {
    render(<CompactFavoriteCard task={makeTask({ status: "in_progress" })} />);
    expect(screen.getByText("in progress")).toBeInTheDocument();
  });

  it("renders a filled star icon", () => {
    const { container } = render(<CompactFavoriteCard task={makeTask()} />);
    const star = container.querySelector(".fill-amber-400");
    expect(star).toBeInTheDocument();
  });

  it("calls toggleFavoriteTask when star is clicked", async () => {
    const user = userEvent.setup();
    const { container } = render(<CompactFavoriteCard task={makeTask()} />);
    const star = container.querySelector(".fill-amber-400")!;
    await user.click(star);
    expect(mockToggleFavoriteTask).toHaveBeenCalledWith("task1");
  });

  it("calls onClick when card is clicked", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<CompactFavoriteCard task={makeTask()} onClick={handleClick} />);
    await user.click(screen.getByTestId("compact-favorite-card"));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("does not call onClick when star is clicked (stopPropagation)", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    const { container } = render(
      <CompactFavoriteCard task={makeTask()} onClick={handleClick} />
    );
    const star = container.querySelector(".fill-amber-400")!;
    await user.click(star);
    expect(handleClick).not.toHaveBeenCalled();
    expect(mockToggleFavoriteTask).toHaveBeenCalledTimes(1);
  });
});

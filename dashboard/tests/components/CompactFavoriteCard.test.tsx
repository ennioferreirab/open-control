import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { testId } from "@/tests/helpers/mockConvex";

// Mock convex/react hooks
// eslint-disable-next-line no-restricted-imports
vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    tasks: {
      toggleFavorite: "tasks:toggleFavorite",
    },
  },
}));

// eslint-disable-next-line no-restricted-imports
import { useMutation } from "convex/react";
import { CompactFavoriteCard } from "../../components/CompactFavoriteCard";

const mockUseMutation = useMutation as ReturnType<typeof vi.fn>;

import type { Doc } from "@/convex/_generated/dataModel";

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    _id: testId<"tasks">("task1"),
    _creationTime: 1700000000000,
    title: "Test Task Title",
    status: "in_progress" as const,
    assignedAgent: "dev-agent",
    trustLevel: "autonomous" as const,
    isFavorite: true,
    createdAt: "2024-01-01T00:00:00.000Z",
    updatedAt: "2024-01-01T00:00:00.000Z",
    ...overrides,
  } as unknown as Doc<"tasks">;
}

describe("CompactFavoriteCard", () => {
  const mockToggleFavorite = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseMutation.mockReturnValue(mockToggleFavorite);
    mockToggleFavorite.mockResolvedValue(undefined);
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

  it("calls toggleFavorite when star is clicked", async () => {
    const user = userEvent.setup();
    const { container } = render(<CompactFavoriteCard task={makeTask()} />);
    const star = container.querySelector(".fill-amber-400")!;
    await user.click(star);
    expect(mockToggleFavorite).toHaveBeenCalledWith({ taskId: "task1" });
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
    const { container } = render(<CompactFavoriteCard task={makeTask()} onClick={handleClick} />);
    const star = container.querySelector(".fill-amber-400")!;
    await user.click(star);
    expect(handleClick).not.toHaveBeenCalled();
    expect(mockToggleFavorite).toHaveBeenCalledTimes(1);
  });
});

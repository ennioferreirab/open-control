import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConvexError } from "convex/values";

// Mock convex/react hooks
vi.mock("convex/react", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    taskTags: {
      list: "taskTags:list",
      create: "taskTags:create",
      remove: "taskTags:remove",
    },
  },
}));

import { useQuery, useMutation } from "convex/react";
import { TagsPanel } from "../../components/TagsPanel";

const mockUseQuery = useQuery as ReturnType<typeof vi.fn>;
const mockUseMutation = useMutation as ReturnType<typeof vi.fn>;

describe("TagsPanel", () => {
  const mockCreateTag = vi.fn();
  const mockRemoveTag = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseMutation.mockImplementation((ref) => {
      if (String(ref).includes("create")) return mockCreateTag;
      if (String(ref).includes("remove")) return mockRemoveTag;
      return vi.fn();
    });
    mockCreateTag.mockResolvedValue(undefined);
    mockRemoveTag.mockResolvedValue(undefined);
  });

  it("shows empty state when no tags exist", () => {
    mockUseQuery.mockReturnValue([]);
    render(<TagsPanel />);
    expect(
      screen.getByText("No tags yet. Add your first tag below.")
    ).toBeInTheDocument();
  });

  it("shows no list when tags are loading (undefined)", () => {
    mockUseQuery.mockReturnValue(undefined);
    render(<TagsPanel />);
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(
      screen.queryByText("No tags yet. Add your first tag below.")
    ).not.toBeInTheDocument();
  });

  it("renders existing tags with name and delete button", () => {
    mockUseQuery.mockReturnValue([
      { _id: "id1", name: "Bug", color: "red" },
      { _id: "id2", name: "Feature", color: "blue" },
    ]);
    render(<TagsPanel />);
    expect(screen.getByText("Bug")).toBeInTheDocument();
    expect(screen.getByText("Feature")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Delete tag/i })).toHaveLength(2);
  });

  it("disables Add button when name input is empty", () => {
    mockUseQuery.mockReturnValue([]);
    const { getByRole } = render(<TagsPanel />);
    // Get the "Add" button specifically (not the color swatches)
    const addButton = getByRole("button", { name: /^Add$/ });
    expect(addButton).toBeDisabled();
  });

  it("enables Add button when name is entered", async () => {
    mockUseQuery.mockReturnValue([]);
    const { getByRole, getByPlaceholderText } = render(<TagsPanel />);
    const input = getByPlaceholderText("Tag name…");
    await userEvent.type(input, "MyTag");
    expect(getByRole("button", { name: /^Add$/ })).not.toBeDisabled();
  });

  it("calls createTag and clears input on successful add", async () => {
    mockUseQuery.mockReturnValue([]);
    const { getByRole, getByPlaceholderText } = render(<TagsPanel />);
    const input = getByPlaceholderText("Tag name…");
    await userEvent.type(input, "NewTag");
    await userEvent.click(getByRole("button", { name: /^Add$/ }));
    expect(mockCreateTag).toHaveBeenCalledWith({
      name: "NewTag",
      color: "blue",
    });
    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("shows 'Tag already exists' error for ConvexError duplicate", async () => {
    mockUseQuery.mockReturnValue([]);
    mockCreateTag.mockRejectedValue(new ConvexError("Tag already exists"));
    const { getByRole, getByPlaceholderText } = render(<TagsPanel />);
    await userEvent.type(getByPlaceholderText("Tag name…"), "Duplicate");
    await userEvent.click(getByRole("button", { name: /^Add$/ }));
    await waitFor(() => {
      expect(screen.getByText("Tag already exists")).toBeInTheDocument();
    });
  });

  it("shows generic error for non-duplicate failures", async () => {
    mockUseQuery.mockReturnValue([]);
    mockCreateTag.mockRejectedValue(new Error("Network error"));
    const { getByRole, getByPlaceholderText } = render(<TagsPanel />);
    await userEvent.type(getByPlaceholderText("Tag name…"), "SomeTag");
    await userEvent.click(getByRole("button", { name: /^Add$/ }));
    await waitFor(() => {
      expect(
        screen.getByText("Failed to create tag. Please try again.")
      ).toBeInTheDocument();
    });
  });

  it("clears error when user starts typing again", async () => {
    mockUseQuery.mockReturnValue([]);
    mockCreateTag.mockRejectedValue(new ConvexError("Tag already exists"));
    const { getByRole, getByPlaceholderText } = render(<TagsPanel />);
    const input = getByPlaceholderText("Tag name…");
    await userEvent.type(input, "Dup");
    await userEvent.click(getByRole("button", { name: /^Add$/ }));
    await waitFor(() => screen.getByText("Tag already exists"));
    await userEvent.type(input, "X");
    expect(screen.queryByText("Tag already exists")).not.toBeInTheDocument();
  });

  it("calls removeTag when delete button is clicked", async () => {
    mockUseQuery.mockReturnValue([{ _id: "id1", name: "Bug", color: "red" }]);
    render(<TagsPanel />);
    await userEvent.click(
      screen.getByRole("button", { name: /Delete tag Bug/i })
    );
    expect(mockRemoveTag).toHaveBeenCalledWith({ id: "id1" });
  });

  it("renders 8 color swatches in the color picker", () => {
    mockUseQuery.mockReturnValue([]);
    render(<TagsPanel />);
    expect(
      screen.getAllByRole("button", { name: /Select color/i })
    ).toHaveLength(8);
  });
});

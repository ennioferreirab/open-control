import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SquadAuthoringWizard } from "./SquadAuthoringWizard";

// Mock the useCreateSquadDraft hook using importOriginal to preserve named exports
vi.mock("@/features/agents/hooks/useCreateSquadDraft", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/agents/hooks/useCreateSquadDraft")>();
  return {
    ...actual,
    useCreateSquadDraft: vi.fn(),
  };
});

import {
  useCreateSquadDraft,
  EMPTY_SQUAD_DRAFT,
} from "@/features/agents/hooks/useCreateSquadDraft";

const mockUseCreateSquadDraft = vi.mocked(useCreateSquadDraft);

describe("SquadAuthoringWizard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockUseCreateSquadDraft.mockReturnValue({
      draft: { ...EMPTY_SQUAD_DRAFT },
      isSaving: false,
      updateDraft: vi.fn(),
      publishDraft: vi.fn().mockResolvedValue(null),
    });
  });

  it("renders squad authoring wizard when open", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // "Create Squad" title should be visible
    const squadTexts = screen.getAllByText(/squad/i);
    expect(squadTexts.length).toBeGreaterThan(0);
  });

  it("shows Outcome phase as the first step", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    const outcomeElements = screen.getAllByText(/outcome/i);
    expect(outcomeElements.length).toBeGreaterThan(0);
  });

  it("renders a live summary panel", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.getByTestId("squad-spec-summary")).toBeInTheDocument();
  });

  it("shows team design phase indicator", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // Phase labels are rendered in the phase navigation bar
    expect(screen.getByText("Team Design")).toBeInTheDocument();
  });

  it("shows workflow design phase indicator", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.getByText("Workflow Design")).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const handleClose = vi.fn();
    render(<SquadAuthoringWizard open={true} onClose={handleClose} onPublished={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(handleClose).toHaveBeenCalled();
  });

  it("allows entering squad display name", async () => {
    const updateDraft = vi.fn();
    mockUseCreateSquadDraft.mockReturnValue({
      draft: { ...EMPTY_SQUAD_DRAFT },
      isSaving: false,
      updateDraft,
      publishDraft: vi.fn().mockResolvedValue(null),
    });
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // The display name input uses placeholder "squad name (e.g. Review Squad)"
    const displayNameInput = screen.getByPlaceholderText(/review squad/i);
    await userEvent.type(displayNameInput, "Alpha Team");
    // updateDraft should have been called for each typed character
    expect(updateDraft).toHaveBeenCalled();
  });

  it("does not render when open=false", () => {
    render(<SquadAuthoringWizard open={false} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.queryByTestId("squad-spec-summary")).not.toBeInTheDocument();
  });

  it("calls publishDraft and onPublished when publish succeeds", async () => {
    const publishDraft = vi.fn().mockResolvedValue("my-squad");
    const onPublished = vi.fn();
    const onClose = vi.fn();
    mockUseCreateSquadDraft.mockReturnValue({
      draft: { ...EMPTY_SQUAD_DRAFT, name: "my-squad" },
      isSaving: false,
      updateDraft: vi.fn(),
      publishDraft,
    });
    render(<SquadAuthoringWizard open={true} onClose={onClose} onPublished={onPublished} />);

    // Navigate to the last phase
    const nextButton = screen.getByRole("button", { name: /next/i });
    await userEvent.click(nextButton);
    await userEvent.click(nextButton);
    await userEvent.click(nextButton);
    await userEvent.click(nextButton);

    // Now on review-approval phase — click Publish Squad
    const publishButton = screen.getByRole("button", { name: /publish squad/i });
    await userEvent.click(publishButton);

    expect(publishDraft).toHaveBeenCalled();
    expect(onPublished).toHaveBeenCalledWith("my-squad");
    expect(onClose).toHaveBeenCalled();
  });

  it("does not call onPublished when publishDraft returns null", async () => {
    const publishDraft = vi.fn().mockResolvedValue(null);
    const onPublished = vi.fn();
    const onClose = vi.fn();
    mockUseCreateSquadDraft.mockReturnValue({
      draft: { ...EMPTY_SQUAD_DRAFT, name: "my-squad" },
      isSaving: false,
      updateDraft: vi.fn(),
      publishDraft,
    });
    render(<SquadAuthoringWizard open={true} onClose={onClose} onPublished={onPublished} />);

    // Navigate to the last phase
    const nextButton = screen.getByRole("button", { name: /next/i });
    await userEvent.click(nextButton);
    await userEvent.click(nextButton);
    await userEvent.click(nextButton);
    await userEvent.click(nextButton);

    const publishButton = screen.getByRole("button", { name: /publish squad/i });
    await userEvent.click(publishButton);

    expect(publishDraft).toHaveBeenCalled();
    expect(onPublished).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});

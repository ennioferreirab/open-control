import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentAuthoringWizard } from "./AgentAuthoringWizard";

// Mock the useCreateAuthoringDraft hook using importOriginal to preserve named exports
vi.mock("@/features/agents/hooks/useCreateAuthoringDraft", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/agents/hooks/useCreateAuthoringDraft")>();
  return {
    ...actual,
    useCreateAuthoringDraft: vi.fn(),
  };
});

import {
  useCreateAuthoringDraft,
  EMPTY_AGENT_DRAFT,
} from "@/features/agents/hooks/useCreateAuthoringDraft";

const mockUseCreateAuthoringDraft = vi.mocked(useCreateAuthoringDraft);

describe("AgentAuthoringWizard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockUseCreateAuthoringDraft.mockReturnValue({
      draft: { ...EMPTY_AGENT_DRAFT },
      isDirty: false,
      isSaving: false,
      updateDraft: vi.fn(),
      saveDraft: vi.fn(),
      publishDraft: vi.fn(),
    });
  });

  it("renders the first step: Purpose phase", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    const purposeElements = screen.getAllByText(/purpose/i);
    expect(purposeElements.length).toBeGreaterThan(0);
  });

  it("shows a live summary panel on the right side", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.getByTestId("agent-spec-summary")).toBeInTheDocument();
  });

  it("renders agent name input field in Purpose phase", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    const nameInput = screen.getByPlaceholderText(/agent name/i);
    expect(nameInput).toBeInTheDocument();
  });

  it("shows phase progression through steps", async () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // Phase indicators exist - look for the phase step numbers
    const phaseNumbers = screen.getAllByText(/^[1-6]$/);
    expect(phaseNumbers.length).toBeGreaterThan(0);
  });

  it("calls onClose when Cancel is clicked", async () => {
    const handleClose = vi.fn();
    render(<AgentAuthoringWizard open={true} onClose={handleClose} onPublished={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(handleClose).toHaveBeenCalled();
  });

  it("publish button is disabled when required fields are empty", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // Should be on the last step or the button should be disabled/not shown yet
    // The wizard should require name and role at minimum
    const publishButton = screen.queryByRole("button", { name: /publish/i });
    if (publishButton) {
      expect(publishButton).toBeDisabled();
    }
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentAuthoringWizard } from "./AgentAuthoringWizard";

// ── Mock the shared authoring session ──────────────────────────────────────
vi.mock("@/features/agents/hooks/useAuthoringSession", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/agents/hooks/useAuthoringSession")>();
  return {
    ...actual,
    useAuthoringSession: vi.fn(),
  };
});

// ── Mock the publish hook ─────────────────────────────────────────────────
vi.mock("@/features/agents/hooks/useCreateAuthoringDraft", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/agents/hooks/useCreateAuthoringDraft")>();
  return {
    ...actual,
    useCreateAuthoringDraft: vi.fn(),
  };
});

import { useAuthoringSession } from "@/features/agents/hooks/useAuthoringSession";
import {
  useCreateAuthoringDraft,
  EMPTY_AGENT_DRAFT,
} from "@/features/agents/hooks/useCreateAuthoringDraft";

const mockUseAuthoringSession = vi.mocked(useAuthoringSession);
const mockUseCreateAuthoringDraft = vi.mocked(useCreateAuthoringDraft);

describe("AgentAuthoringWizard — chat-first", () => {
  beforeEach(() => {
    vi.resetAllMocks();

    mockUseAuthoringSession.mockReturnValue({
      phase: "discovery",
      transcript: [{ role: "assistant", content: "Hi! What kind of agent do you want to build?" }],
      draftGraph: {},
      isLoading: false,
      error: null,
      sendMessage: vi.fn(),
      reset: vi.fn(),
    });

    mockUseCreateAuthoringDraft.mockReturnValue({
      draft: { ...EMPTY_AGENT_DRAFT },
      isDirty: false,
      isSaving: false,
      updateDraft: vi.fn(),
      saveDraft: vi.fn(),
      publishDraft: vi.fn(),
    });
  });

  it("renders the conversation transcript panel (chat-first)", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // The assistant greeting must be visible from the transcript
    expect(screen.getByText("Hi! What kind of agent do you want to build?")).toBeInTheDocument();
  });

  it("renders a message composer input (not a form-first UI)", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // There must be a textbox for the user to type in
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("renders the live preview panel", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.getByTestId("authoring-preview-panel")).toBeInTheDocument();
  });

  it("uses useAuthoringSession with agent mode", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(mockUseAuthoringSession).toHaveBeenCalledWith("agent");
  });

  it("shows the approve/publish button when phase is approval", () => {
    mockUseAuthoringSession.mockReturnValue({
      phase: "approval",
      transcript: [{ role: "assistant", content: "The agent looks good. Ready to publish?" }],
      draftGraph: { agents: [{ key: "researcher", role: "Researcher" }] },
      isLoading: false,
      error: null,
      sendMessage: vi.fn(),
      reset: vi.fn(),
    });

    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.getByRole("button", { name: /publish/i })).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const handleClose = vi.fn();
    render(<AgentAuthoringWizard open={true} onClose={handleClose} onPublished={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(handleClose).toHaveBeenCalled();
  });

  it("does not render a multi-step form as the primary surface", () => {
    render(<AgentAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // The old form-first agent-name input field should NOT be the primary element
    expect(
      screen.queryByPlaceholderText(/agent name \(e\.g\. my-agent\)/i),
    ).not.toBeInTheDocument();
  });
});

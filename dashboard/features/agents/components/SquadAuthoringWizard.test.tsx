import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SquadAuthoringWizard } from "./SquadAuthoringWizard";

// ── Mock the shared authoring session ──────────────────────────────────────
vi.mock("@/features/agents/hooks/useAuthoringSession", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/agents/hooks/useAuthoringSession")>();
  return {
    ...actual,
    useAuthoringSession: vi.fn(),
  };
});

// ── Mock the squad publish hook ─────────────────────────────────────────────
vi.mock("@/features/agents/hooks/useCreateSquadDraft", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/agents/hooks/useCreateSquadDraft")>();
  return {
    ...actual,
    useCreateSquadDraft: vi.fn(),
  };
});

import { useAuthoringSession } from "@/features/agents/hooks/useAuthoringSession";
import { useCreateSquadDraft } from "@/features/agents/hooks/useCreateSquadDraft";

const mockUseAuthoringSession = vi.mocked(useAuthoringSession);
const mockUseCreateSquadDraft = vi.mocked(useCreateSquadDraft);

describe("SquadAuthoringWizard — chat-first", () => {
  beforeEach(() => {
    vi.resetAllMocks();

    mockUseAuthoringSession.mockReturnValue({
      phase: "discovery",
      transcript: [
        {
          role: "assistant",
          content: "Hi! Tell me about the squad you want to build.",
        },
      ],
      draftGraph: {},
      isLoading: false,
      error: null,
      sendMessage: vi.fn(),
      reset: vi.fn(),
      readiness: 0,
      patchDraftGraph: vi.fn(),
    });

    mockUseCreateSquadDraft.mockReturnValue({
      draft: {
        name: "",
        displayName: "",
        description: "",
        outcome: "",
        agentRoles: [],
        workflowSteps: [],
        exitCriteria: "",
        reviewPolicy: "",
      },
      isSaving: false,
      updateDraft: vi.fn(),
      publishDraft: vi.fn().mockResolvedValue(null),
    });
  });

  it("renders the conversation transcript panel (chat-first)", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.getByText("Hi! Tell me about the squad you want to build.")).toBeInTheDocument();
  });

  it("renders a message composer input (not a form-first UI)", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // There must be a textbox for the user to type in
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("renders the live preview panel", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.getByTestId("authoring-preview-panel")).toBeInTheDocument();
  });

  it("uses useAuthoringSession with squad mode", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(mockUseAuthoringSession).toHaveBeenCalledWith("squad");
  });

  it("does NOT render a multi-step form as the primary surface (not form-first)", () => {
    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    // Old form-first phase labels should NOT be the primary interaction
    expect(screen.queryByText("Team Design")).not.toBeInTheDocument();
    expect(screen.queryByText("Workflow Design")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/review squad/i)).not.toBeInTheDocument();
  });

  it("shows the approve/publish button when phase is approval", () => {
    mockUseAuthoringSession.mockReturnValue({
      phase: "approval",
      transcript: [
        {
          role: "assistant",
          content: "The squad looks great! Ready to publish?",
        },
      ],
      draftGraph: {
        squad: { outcome: "Build great software" },
        agents: [{ key: "developer", role: "Developer" }],
        workflows: [{ key: "default", steps: [] }],
      },
      isLoading: false,
      error: null,
      sendMessage: vi.fn(),
      reset: vi.fn(),
      readiness: 80,
      patchDraftGraph: vi.fn(),
    });

    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.getByRole("button", { name: /publish/i })).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const handleClose = vi.fn();
    render(<SquadAuthoringWizard open={true} onClose={handleClose} onPublished={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(handleClose).toHaveBeenCalled();
  });

  it("does not render when open=false", () => {
    render(<SquadAuthoringWizard open={false} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.queryByTestId("authoring-preview-panel")).not.toBeInTheDocument();
  });

  it("shows preview panel with agents from draftGraph", () => {
    mockUseAuthoringSession.mockReturnValue({
      phase: "proposal",
      transcript: [
        {
          role: "assistant",
          content: "I propose a developer and a reviewer.",
        },
      ],
      draftGraph: {
        agents: [
          { key: "developer", role: "Developer" },
          { key: "reviewer", role: "Reviewer" },
        ],
        workflows: [{ key: "default", steps: [] }],
      },
      isLoading: false,
      error: null,
      sendMessage: vi.fn(),
      reset: vi.fn(),
      readiness: 50,
      patchDraftGraph: vi.fn(),
    });

    render(<SquadAuthoringWizard open={true} onClose={vi.fn()} onPublished={vi.fn()} />);
    expect(screen.getByTestId("authoring-preview-panel")).toBeInTheDocument();
  });

  it("calls publishDraft and onPublished when publish succeeds", async () => {
    const publishDraft = vi.fn().mockResolvedValue("my-squad");
    const onPublished = vi.fn();
    const onClose = vi.fn();
    mockUseAuthoringSession.mockReturnValue({
      phase: "approval",
      transcript: [{ role: "assistant", content: "Ready to publish?" }],
      draftGraph: {
        squad: { name: "my-squad", displayName: "My Squad", outcome: "Build great software" },
        agents: [{ key: "dev", name: "dev", role: "Developer" }],
        workflows: [],
      },
      isLoading: false,
      error: null,
      sendMessage: vi.fn(),
      reset: vi.fn(),
      readiness: 100,
      patchDraftGraph: vi.fn(),
    });
    mockUseCreateSquadDraft.mockReturnValue({
      draft: {
        name: "my-squad",
        displayName: "My Squad",
        description: "",
        outcome: "",
        agentRoles: [],
        workflowSteps: [],
        exitCriteria: "",
        reviewPolicy: "",
      },
      isSaving: false,
      updateDraft: vi.fn(),
      publishDraft,
    });

    render(<SquadAuthoringWizard open={true} onClose={onClose} onPublished={onPublished} />);
    const publishButton = screen.getByRole("button", { name: /publish/i });
    await userEvent.click(publishButton);

    expect(publishDraft).toHaveBeenCalled();
    expect(onPublished).toHaveBeenCalledWith("my-squad");
    expect(onClose).toHaveBeenCalled();
  });

  it("does not call onPublished when publishDraft returns null", async () => {
    const publishDraft = vi.fn().mockResolvedValue(null);
    const onPublished = vi.fn();
    const onClose = vi.fn();
    mockUseAuthoringSession.mockReturnValue({
      phase: "approval",
      transcript: [{ role: "assistant", content: "Ready to publish?" }],
      draftGraph: {},
      isLoading: false,
      error: null,
      sendMessage: vi.fn(),
      reset: vi.fn(),
      readiness: 0,
      patchDraftGraph: vi.fn(),
    });
    mockUseCreateSquadDraft.mockReturnValue({
      draft: {
        name: "",
        displayName: "",
        description: "",
        outcome: "",
        agentRoles: [],
        workflowSteps: [],
        exitCriteria: "",
        reviewPolicy: "",
      },
      isSaving: false,
      updateDraft: vi.fn(),
      publishDraft,
    });

    render(<SquadAuthoringWizard open={true} onClose={onClose} onPublished={onPublished} />);
    const publishButton = screen.getByRole("button", { name: /publish/i });
    await userEvent.click(publishButton);

    expect(publishDraft).toHaveBeenCalled();
    expect(onPublished).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});

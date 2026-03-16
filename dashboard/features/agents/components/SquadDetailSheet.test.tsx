import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SquadDetailSheet } from "./SquadDetailSheet";

vi.mock("@/features/agents/hooks/useUpdatePublishedSquad", () => ({
  useUpdatePublishedSquad: vi.fn(),
}));

// Mock useSquadDetailData
vi.mock("@/features/agents/hooks/useSquadDetailData", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/agents/hooks/useSquadDetailData")>();
  return {
    ...actual,
    useSquadDetailData: vi.fn(),
  };
});

import { useSquadDetailData } from "@/features/agents/hooks/useSquadDetailData";
import { useUpdatePublishedSquad } from "@/features/agents/hooks/useUpdatePublishedSquad";
import type { Id } from "@/convex/_generated/dataModel";

const mockUseSquadDetailData = vi.mocked(useSquadDetailData);
const mockUseUpdatePublishedSquad = vi.mocked(useUpdatePublishedSquad);

const MOCK_SQUAD_ID = "squad-spec-id-1" as Id<"squadSpecs">;
const mockPublish = vi.fn().mockResolvedValue(MOCK_SQUAD_ID);

function makeLoadedState() {
  return {
    squad: {
      _id: MOCK_SQUAD_ID,
      _creationTime: 1000,
      name: "review-squad",
      displayName: "Review Squad",
      description: "A squad for reviewing code",
      outcome: "Ship quality code",
      agentIds: ["agent-1" as Id<"agents">],
      defaultWorkflowSpecId: "wf-1" as Id<"workflowSpecs">,
      status: "published" as const,
      version: 1,
      createdAt: "2024-01-01",
      updatedAt: "2024-01-01",
    },
    workflows: [
      {
        _id: "wf-1" as Id<"workflowSpecs">,
        _creationTime: 1000,
        squadSpecId: MOCK_SQUAD_ID,
        name: "Default Workflow",
        description: "The main workflow",
        steps: [
          {
            id: "step-1",
            title: "Review",
            description: "Review the output",
            type: "review" as const,
            agentId: "agent-1" as Id<"agents">,
            reviewSpecId: "review-spec-1" as Id<"reviewSpecs">,
            onReject: "step-2",
          },
          {
            id: "step-2",
            title: "Revise",
            type: "agent" as const,
            agentId: "agent-1" as Id<"agents">,
          },
        ],
        status: "published" as const,
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
    ],
    agents: [
      {
        _id: "agent-1" as Id<"agents">,
        _creationTime: 1000,
        name: "reviewer",
        displayName: "Code Reviewer",
        role: "QA Engineer",
        prompt: "Review things",
        skills: ["code-review"],
        status: "idle" as const,
        enabled: true,
        model: "cc/claude-sonnet-4-6",
      },
    ],
    isLoading: false,
  };
}

describe("SquadDetailSheet", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockUseUpdatePublishedSquad.mockReturnValue({
      isPublishing: false,
      publish: mockPublish,
    });
  });

  it("does not render when squadId is null", () => {
    mockUseSquadDetailData.mockReturnValue({
      squad: null,
      workflows: [],
      agents: [],
      isLoading: false,
    });
    const { container } = render(<SquadDetailSheet squadId={null} onClose={vi.fn()} />);
    expect(container.querySelector("[data-testid='squad-detail-sheet']")).not.toBeInTheDocument();
  });

  it("shows loading state while squad data is loading", () => {
    mockUseSquadDetailData.mockReturnValue({
      squad: undefined,
      workflows: undefined,
      agents: undefined,
      isLoading: true,
    });
    render(<SquadDetailSheet squadId={MOCK_SQUAD_ID} onClose={vi.fn()} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders squad display name and status badge", () => {
    mockUseSquadDetailData.mockReturnValue({
      squad: {
        _id: MOCK_SQUAD_ID,
        _creationTime: 1000,
        name: "review-squad",
        displayName: "Review Squad",
        description: "A squad for reviewing code",
        outcome: "Ship quality code",
        agentIds: ["agent-1" as Id<"agents">, "agent-2" as Id<"agents">],
        defaultWorkflowSpecId: undefined,
        status: "published",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
      workflows: [],
      agents: [],
      isLoading: false,
    });
    render(<SquadDetailSheet squadId={MOCK_SQUAD_ID} onClose={vi.fn()} />);
    expect(screen.getByText("Review Squad")).toBeInTheDocument();
    expect(screen.getByText("published")).toBeInTheDocument();
  });

  it("shows non-empty agent count when agents are persisted", () => {
    mockUseSquadDetailData.mockReturnValue({
      squad: {
        _id: MOCK_SQUAD_ID,
        _creationTime: 1000,
        name: "review-squad",
        displayName: "Review Squad",
        description: undefined,
        outcome: undefined,
        agentIds: ["agent-1" as Id<"agents">, "agent-2" as Id<"agents">],
        defaultWorkflowSpecId: undefined,
        status: "published",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
      workflows: [],
      agents: [
        {
          _id: "agent-1" as Id<"agents">,
          _creationTime: 1000,
          name: "developer",
          displayName: "Senior Developer",
          role: "Backend Engineer",
          skills: ["python"],
          status: "idle",
          lastActiveAt: "2024-01-01",
        },
        {
          _id: "agent-2" as Id<"agents">,
          _creationTime: 1001,
          name: "reviewer",
          displayName: "Code Reviewer",
          role: "QA Engineer",
          skills: ["code-review"],
          status: "idle",
          lastActiveAt: "2024-01-01",
        },
      ],
      isLoading: false,
    });
    render(<SquadDetailSheet squadId={MOCK_SQUAD_ID} onClose={vi.fn()} />);
    // Should show agent display names, not "No agents defined yet"
    expect(screen.getByText("Senior Developer")).toBeInTheDocument();
    expect(screen.getByText("Code Reviewer")).toBeInTheDocument();
    expect(screen.queryByText(/no agents defined/i)).not.toBeInTheDocument();
  });

  it("shows non-empty workflow list when workflows are persisted", () => {
    mockUseSquadDetailData.mockReturnValue({
      squad: {
        _id: MOCK_SQUAD_ID,
        _creationTime: 1000,
        name: "review-squad",
        displayName: "Review Squad",
        description: undefined,
        outcome: undefined,
        agentIds: [],
        defaultWorkflowSpecId: "wf-1" as Id<"workflowSpecs">,
        status: "published",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
      workflows: [
        {
          _id: "wf-1" as Id<"workflowSpecs">,
          _creationTime: 1000,
          squadSpecId: MOCK_SQUAD_ID,
          name: "Default Workflow",
          description: "The main workflow",
          steps: [
            { id: "step-1", title: "Review", type: "review" as const },
            { id: "step-2", title: "Approve", type: "human" as const },
          ],
          status: "published",
          version: 1,
          createdAt: "2024-01-01",
          updatedAt: "2024-01-01",
        },
      ],
      agents: [],
      isLoading: false,
    });
    render(<SquadDetailSheet squadId={MOCK_SQUAD_ID} onClose={vi.fn()} />);
    expect(screen.getByText("Default Workflow")).toBeInTheDocument();
    expect(screen.queryByText(/no workflows defined/i)).not.toBeInTheDocument();
  });

  it("shows outcome when available", () => {
    mockUseSquadDetailData.mockReturnValue({
      squad: {
        _id: MOCK_SQUAD_ID,
        _creationTime: 1000,
        name: "review-squad",
        displayName: "Review Squad",
        description: undefined,
        outcome: "Ship quality code consistently",
        agentIds: [],
        defaultWorkflowSpecId: undefined,
        status: "published",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
      workflows: [],
      agents: [],
      isLoading: false,
    });
    render(<SquadDetailSheet squadId={MOCK_SQUAD_ID} onClose={vi.fn()} />);
    expect(screen.getByText("Ship quality code consistently")).toBeInTheDocument();
  });

  it("shows empty state when no agents defined", () => {
    mockUseSquadDetailData.mockReturnValue({
      squad: {
        _id: MOCK_SQUAD_ID,
        _creationTime: 1000,
        name: "review-squad",
        displayName: "Review Squad",
        description: undefined,
        outcome: undefined,
        agentIds: [],
        defaultWorkflowSpecId: undefined,
        status: "published",
        version: 1,
        createdAt: "2024-01-01",
        updatedAt: "2024-01-01",
      },
      workflows: [],
      agents: [],
      isLoading: false,
    });
    render(<SquadDetailSheet squadId={MOCK_SQUAD_ID} onClose={vi.fn()} />);
    expect(screen.getByText(/no agents defined/i)).toBeInTheDocument();
  });

  it("publishes edited workflow data instead of showing a save action", async () => {
    mockUseSquadDetailData.mockReturnValue(makeLoadedState());
    render(<SquadDetailSheet squadId={MOCK_SQUAD_ID} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /edit squad/i }));

    const workflowNameInput = screen.getByLabelText(/workflow name/i);
    const firstStepTitleInput = screen.getByLabelText(/step 1 title/i);

    await userEvent.clear(workflowNameInput);
    await userEvent.type(workflowNameInput, "Edited Workflow");
    await userEvent.clear(firstStepTitleInput);
    await userEvent.type(firstStepTitleInput, "Edited Review");

    expect(screen.queryByRole("button", { name: /^save$/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /publicar/i }));

    expect(mockPublish).toHaveBeenCalledWith(
      expect.objectContaining({
        squadSpecId: MOCK_SQUAD_ID,
        graph: expect.objectContaining({
          workflows: [
            expect.objectContaining({
              id: "wf-1",
              name: "Edited Workflow",
              steps: expect.arrayContaining([
                expect.objectContaining({
                  key: "step-1",
                  title: "Edited Review",
                  type: "review",
                }),
              ]),
            }),
          ],
        }),
      }),
    );
  });

  it("allows inserting a checkpoint step from squad editing", async () => {
    mockUseSquadDetailData.mockReturnValue(makeLoadedState());
    render(<SquadDetailSheet squadId={MOCK_SQUAD_ID} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /edit squad/i }));
    await userEvent.click(screen.getByRole("button", { name: /add step/i }));

    await userEvent.clear(screen.getByLabelText(/step 3 title/i));
    await userEvent.type(screen.getByLabelText(/step 3 title/i), "Quality Gate");
    await userEvent.selectOptions(screen.getByLabelText(/step 3 type/i), "checkpoint");

    await userEvent.click(screen.getByRole("button", { name: /publicar/i }));

    expect(mockPublish).toHaveBeenCalledWith(
      expect.objectContaining({
        graph: expect.objectContaining({
          workflows: [
            expect.objectContaining({
              steps: expect.arrayContaining([
                expect.objectContaining({
                  key: expect.stringMatching(/^step-/),
                  title: "Quality Gate",
                  type: "checkpoint",
                }),
              ]),
            }),
          ],
        }),
      }),
    );
  });

  it("switches to the selected agent tab when clicking an agent in squad context", async () => {
    mockUseSquadDetailData.mockReturnValue(makeLoadedState());
    render(<SquadDetailSheet squadId={MOCK_SQUAD_ID} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /code reviewer/i }));

    expect(screen.getByRole("tab", { name: /agent/i })).toHaveAttribute("data-state", "active");
    expect(screen.getByText("Back to squad")).toBeInTheDocument();
    expect(screen.getByText("Code Reviewer")).toBeInTheDocument();
    expect(screen.getByText("reviewer")).toBeInTheDocument();
  });
});

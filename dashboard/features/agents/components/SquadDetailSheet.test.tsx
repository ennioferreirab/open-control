import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { SquadDetailSheet } from "./SquadDetailSheet";

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
import type { Id } from "@/convex/_generated/dataModel";

const mockUseSquadDetailData = vi.mocked(useSquadDetailData);

const MOCK_SQUAD_ID = "squad-spec-id-1" as Id<"squadSpecs">;

describe("SquadDetailSheet", () => {
  beforeEach(() => {
    vi.resetAllMocks();
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
});

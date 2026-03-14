import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { Id } from "@/convex/_generated/dataModel";

// Mock the hook
vi.mock("@/features/agents/hooks/useRunSquadMission", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/agents/hooks/useRunSquadMission")>();
  return {
    ...actual,
    useRunSquadMission: vi.fn(),
  };
});

import { useRunSquadMission } from "@/features/agents/hooks/useRunSquadMission";
import { RunSquadMissionDialog } from "./RunSquadMissionDialog";

const mockUseRunSquadMission = vi.mocked(useRunSquadMission);

const MOCK_SQUAD_ID = "squad-spec-id-1" as Id<"squadSpecs">;
const MOCK_BOARD_ID = "board-id-1" as Id<"boards">;
const MOCK_WORKFLOW_ID = "workflow-spec-id-1" as Id<"workflowSpecs">;
const MOCK_TASK_ID = "task-id-1" as Id<"tasks">;

describe("RunSquadMissionDialog", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("does not render content when open is false", () => {
    mockUseRunSquadMission.mockReturnValue({
      isLaunching: false,
      effectiveWorkflowId: MOCK_WORKFLOW_ID,
      launch: vi.fn(),
    });

    const { queryByRole } = render(
      <RunSquadMissionDialog
        open={false}
        onClose={vi.fn()}
        onLaunched={vi.fn()}
        squadSpecId={MOCK_SQUAD_ID}
        squadDisplayName="Review Squad"
        boardId={MOCK_BOARD_ID}
      />,
    );

    expect(queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the dialog with squad display name when open", () => {
    mockUseRunSquadMission.mockReturnValue({
      isLaunching: false,
      effectiveWorkflowId: MOCK_WORKFLOW_ID,
      launch: vi.fn(),
    });

    render(
      <RunSquadMissionDialog
        open={true}
        onClose={vi.fn()}
        onLaunched={vi.fn()}
        squadSpecId={MOCK_SQUAD_ID}
        squadDisplayName="Review Squad"
        boardId={MOCK_BOARD_ID}
      />,
    );

    expect(screen.getByText("Run Squad Mission")).toBeInTheDocument();
    expect(screen.getByText("Review Squad")).toBeInTheDocument();
  });

  it("disables the Launch Mission button when title is empty", () => {
    mockUseRunSquadMission.mockReturnValue({
      isLaunching: false,
      effectiveWorkflowId: MOCK_WORKFLOW_ID,
      launch: vi.fn(),
    });

    render(
      <RunSquadMissionDialog
        open={true}
        onClose={vi.fn()}
        onLaunched={vi.fn()}
        squadSpecId={MOCK_SQUAD_ID}
        squadDisplayName="Review Squad"
        boardId={MOCK_BOARD_ID}
      />,
    );

    const launchButton = screen.getByRole("button", { name: /launch mission/i });
    expect(launchButton).toBeDisabled();
  });

  it("enables the Launch Mission button when title is filled and workflow exists", () => {
    mockUseRunSquadMission.mockReturnValue({
      isLaunching: false,
      effectiveWorkflowId: MOCK_WORKFLOW_ID,
      launch: vi.fn(),
    });

    render(
      <RunSquadMissionDialog
        open={true}
        onClose={vi.fn()}
        onLaunched={vi.fn()}
        squadSpecId={MOCK_SQUAD_ID}
        squadDisplayName="Review Squad"
        boardId={MOCK_BOARD_ID}
      />,
    );

    const titleInput = screen.getByPlaceholderText(/review q4 release plan/i);
    fireEvent.change(titleInput, { target: { value: "Mission Alpha" } });

    const launchButton = screen.getByRole("button", { name: /launch mission/i });
    expect(launchButton).not.toBeDisabled();
  });

  it("calls launch with the correct args when Launch Mission is clicked", async () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseRunSquadMission.mockReturnValue({
      isLaunching: false,
      effectiveWorkflowId: MOCK_WORKFLOW_ID,
      launch: mockLaunch,
    });

    const onLaunched = vi.fn();

    render(
      <RunSquadMissionDialog
        open={true}
        onClose={vi.fn()}
        onLaunched={onLaunched}
        squadSpecId={MOCK_SQUAD_ID}
        squadDisplayName="Review Squad"
        boardId={MOCK_BOARD_ID}
      />,
    );

    const titleInput = screen.getByPlaceholderText(/review q4 release plan/i);
    fireEvent.change(titleInput, { target: { value: "Mission Alpha" } });

    const launchButton = screen.getByRole("button", { name: /launch mission/i });
    fireEvent.click(launchButton);

    await waitFor(() => {
      expect(mockLaunch).toHaveBeenCalledWith({
        squadSpecId: MOCK_SQUAD_ID,
        workflowSpecId: MOCK_WORKFLOW_ID,
        boardId: MOCK_BOARD_ID,
        title: "Mission Alpha",
        description: undefined,
      });
    });
  });

  it("calls onLaunched with the task id after successful launch", async () => {
    const mockLaunch = vi.fn().mockResolvedValue(MOCK_TASK_ID);
    mockUseRunSquadMission.mockReturnValue({
      isLaunching: false,
      effectiveWorkflowId: MOCK_WORKFLOW_ID,
      launch: mockLaunch,
    });

    const onLaunched = vi.fn();

    render(
      <RunSquadMissionDialog
        open={true}
        onClose={vi.fn()}
        onLaunched={onLaunched}
        squadSpecId={MOCK_SQUAD_ID}
        squadDisplayName="Review Squad"
        boardId={MOCK_BOARD_ID}
      />,
    );

    const titleInput = screen.getByPlaceholderText(/review q4 release plan/i);
    fireEvent.change(titleInput, { target: { value: "Mission Alpha" } });

    fireEvent.click(screen.getByRole("button", { name: /launch mission/i }));

    await waitFor(() => {
      expect(onLaunched).toHaveBeenCalledWith(MOCK_TASK_ID);
    });
  });

  it("shows Launching... on the button while isLaunching is true", () => {
    mockUseRunSquadMission.mockReturnValue({
      isLaunching: true,
      effectiveWorkflowId: MOCK_WORKFLOW_ID,
      launch: vi.fn(),
    });

    render(
      <RunSquadMissionDialog
        open={true}
        onClose={vi.fn()}
        onLaunched={vi.fn()}
        squadSpecId={MOCK_SQUAD_ID}
        squadDisplayName="Review Squad"
        boardId={MOCK_BOARD_ID}
      />,
    );

    expect(screen.getByRole("button", { name: /launching/i })).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", () => {
    mockUseRunSquadMission.mockReturnValue({
      isLaunching: false,
      effectiveWorkflowId: MOCK_WORKFLOW_ID,
      launch: vi.fn(),
    });

    const onClose = vi.fn();

    render(
      <RunSquadMissionDialog
        open={true}
        onClose={onClose}
        onLaunched={vi.fn()}
        squadSpecId={MOCK_SQUAD_ID}
        squadDisplayName="Review Squad"
        boardId={MOCK_BOARD_ID}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });
});

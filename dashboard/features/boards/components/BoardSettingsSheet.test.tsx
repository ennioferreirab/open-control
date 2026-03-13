import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mockOpenArtifact = vi.fn();
const mockCloseArtifactViewer = vi.fn();
const mockUploadArtifacts = vi.fn();

vi.mock("@/features/boards/hooks/useBoardSettingsSheet", () => ({
  useBoardSettingsSheet: () => ({
    board: { name: "default" },
    confirmDelete: false,
    description: "",
    displayName: "Default",
    enabledAgents: [],
    error: "",
    getAgentMode: () => "clean",
    handleDelete: vi.fn(),
    handleSave: vi.fn(),
    isDefault: true,
    nonSystemAgents: [],
    saving: false,
    setConfirmDelete: vi.fn(),
    setDescription: vi.fn(),
    setDisplayName: vi.fn(),
    toggleAgent: vi.fn(),
    toggleAgentMode: vi.fn(),
    artifacts: [{ name: "brief.md", path: "templates/brief.md", size: 128, type: "text/markdown" }],
    artifactsLoading: false,
    artifactsError: "",
    selectedArtifact: null,
    openArtifact: mockOpenArtifact,
    closeArtifactViewer: mockCloseArtifactViewer,
    uploadArtifacts: mockUploadArtifacts,
    isUploadingArtifacts: false,
    uploadArtifactsError: "",
    artifactSource: { kind: "board-artifact", boardName: "default" },
  }),
}));

vi.mock("@/components/DocumentViewerModal", () => ({
  DocumentViewerModal: ({
    source,
    file,
  }: {
    source: { kind: string; boardName: string };
    file: { name: string } | null;
    onClose: () => void;
  }) =>
    file ? (
      <div data-testid="artifact-viewer" data-kind={source.kind} data-board={source.boardName}>
        {file.name}
      </div>
    ) : null,
}));

import { BoardSettingsSheet } from "./BoardSettingsSheet";

describe("BoardSettingsSheet", () => {
  it("renders board artifacts and opens them from board settings", () => {
    render(<BoardSettingsSheet open onClose={vi.fn()} />);

    const artifact = screen.getByText("brief.md");
    expect(artifact).toBeInTheDocument();

    fireEvent.click(artifact);

    expect(mockOpenArtifact).toHaveBeenCalledWith(
      expect.objectContaining({ path: "templates/brief.md" }),
    );
  });

  it("offers an upload action for board artifacts", () => {
    render(<BoardSettingsSheet open onClose={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Upload artifact" })).toBeInTheDocument();
  });
});

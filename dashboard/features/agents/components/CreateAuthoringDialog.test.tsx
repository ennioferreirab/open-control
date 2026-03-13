import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateAuthoringDialog } from "./CreateAuthoringDialog";

describe("CreateAuthoringDialog", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("does not render when open=false", () => {
    render(
      <CreateAuthoringDialog
        open={false}
        onClose={vi.fn()}
        onSelectAgent={vi.fn()}
        onSelectSquad={vi.fn()}
      />,
    );
    expect(screen.queryByText("Create Agent")).not.toBeInTheDocument();
    expect(screen.queryByText("Create Squad")).not.toBeInTheDocument();
  });

  it("renders both Create Agent and Create Squad options when open", () => {
    render(
      <CreateAuthoringDialog
        open={true}
        onClose={vi.fn()}
        onSelectAgent={vi.fn()}
        onSelectSquad={vi.fn()}
      />,
    );
    expect(screen.getByText("Create Agent")).toBeInTheDocument();
    expect(screen.getByText("Create Squad")).toBeInTheDocument();
  });

  it("calls onSelectAgent when Create Agent is clicked", async () => {
    const handleAgent = vi.fn();
    render(
      <CreateAuthoringDialog
        open={true}
        onClose={vi.fn()}
        onSelectAgent={handleAgent}
        onSelectSquad={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /create agent/i }));
    expect(handleAgent).toHaveBeenCalled();
  });

  it("calls onSelectSquad when Create Squad is clicked", async () => {
    const handleSquad = vi.fn();
    render(
      <CreateAuthoringDialog
        open={true}
        onClose={vi.fn()}
        onSelectAgent={vi.fn()}
        onSelectSquad={handleSquad}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /create squad/i }));
    expect(handleSquad).toHaveBeenCalled();
  });

  it("calls onClose when dialog is dismissed", async () => {
    const handleClose = vi.fn();
    render(
      <CreateAuthoringDialog
        open={true}
        onClose={handleClose}
        onSelectAgent={vi.fn()}
        onSelectSquad={vi.fn()}
      />,
    );
    // Press Escape to close
    await userEvent.keyboard("{Escape}");
    expect(handleClose).toHaveBeenCalled();
  });
});

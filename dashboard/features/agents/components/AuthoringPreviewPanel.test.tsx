import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthoringPreviewPanel } from "./AuthoringPreviewPanel";

describe("AuthoringPreviewPanel", () => {
  it("renders an empty state when the draft graph is empty", () => {
    render(<AuthoringPreviewPanel draftGraph={{}} phase="discovery" readiness={0} />);
    expect(screen.getByTestId("authoring-preview-panel")).toBeInTheDocument();
  });

  it("shows agent name when draftGraph has an agent with a name", () => {
    const draftGraph = {
      agents: [{ key: "researcher", role: "Research Analyst", name: "Researcher" }],
    };
    render(<AuthoringPreviewPanel draftGraph={draftGraph} phase="proposal" readiness={0.4} />);
    expect(screen.getByText(/researcher/i)).toBeInTheDocument();
  });

  it("shows agent role when present", () => {
    const draftGraph = {
      agents: [{ key: "researcher", role: "Research Analyst" }],
    };
    render(<AuthoringPreviewPanel draftGraph={draftGraph} phase="proposal" readiness={0.4} />);
    expect(screen.getByText(/research analyst/i)).toBeInTheDocument();
  });

  it("shows readiness indicator", () => {
    render(
      <AuthoringPreviewPanel
        draftGraph={{ agents: [{ key: "x", role: "Tester" }] }}
        phase="refinement"
        readiness={0.75}
      />,
    );
    expect(screen.getByTestId("readiness-indicator")).toBeInTheDocument();
  });

  it("shows current phase label", () => {
    render(<AuthoringPreviewPanel draftGraph={{}} phase="approval" readiness={1} />);
    expect(screen.getByText(/approval/i)).toBeInTheDocument();
  });
});

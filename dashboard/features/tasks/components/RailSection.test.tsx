import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FileText } from "lucide-react";
import { RailSection } from "./RailSection";

describe("RailSection", () => {
  it("renders label and icon", () => {
    render(
      <RailSection icon={FileText} label="Files">
        <p>content</p>
      </RailSection>,
    );
    expect(screen.getByText("Files")).toBeDefined();
  });

  it("starts collapsed by default", () => {
    render(
      <RailSection icon={FileText} label="Files">
        <p>hidden content</p>
      </RailSection>,
    );
    const content = screen.getByTestId("rail-section-content");
    expect(content.getAttribute("data-state")).toBe("closed");
  });

  it("expands when header clicked", async () => {
    const user = userEvent.setup();
    render(
      <RailSection icon={FileText} label="Files">
        <p>visible content</p>
      </RailSection>,
    );
    await user.click(screen.getByTestId("rail-section-header"));
    const content = screen.getByTestId("rail-section-content");
    expect(content.getAttribute("data-state")).toBe("open");
    expect(screen.getByText("visible content")).toBeDefined();
  });

  it("starts expanded when defaultOpen is true", () => {
    render(
      <RailSection icon={FileText} label="Files" defaultOpen>
        <p>expanded content</p>
      </RailSection>,
    );
    const content = screen.getByTestId("rail-section-content");
    expect(content.getAttribute("data-state")).toBe("open");
    expect(screen.getByText("expanded content")).toBeDefined();
  });

  it("shows badge when provided", () => {
    render(
      <RailSection icon={FileText} label="Files" badge={5}>
        <p>content</p>
      </RailSection>,
    );
    expect(screen.getByText("5")).toBeDefined();
  });
});

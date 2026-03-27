import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MobileBottomNav } from "./MobileBottomNav";

describe("MobileBottomNav", () => {
  it("renders all 4 tabs", () => {
    render(<MobileBottomNav activeTab="thread" onTabChange={vi.fn()} />);
    expect(screen.getByTestId("tab-thread")).toBeInTheDocument();
    expect(screen.getByTestId("tab-plan")).toBeInTheDocument();
    expect(screen.getByTestId("tab-files")).toBeInTheDocument();
    expect(screen.getByTestId("tab-live")).toBeInTheDocument();
  });

  it("calls onTabChange when tab clicked", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(<MobileBottomNav activeTab="thread" onTabChange={onTabChange} />);
    await user.click(screen.getByTestId("tab-plan"));
    expect(onTabChange).toHaveBeenCalledWith("plan");
  });

  it("shows active styling on selected tab", () => {
    render(<MobileBottomNav activeTab="thread" onTabChange={vi.fn()} />);
    expect(screen.getByTestId("tab-thread").className).toContain("text-primary");
    expect(screen.getByTestId("tab-plan").className).toContain("text-muted-foreground");
    expect(screen.getByTestId("accent-thread")).toBeInTheDocument();
  });

  it("shows green dot when hasLiveSession is true", () => {
    render(<MobileBottomNav activeTab="thread" onTabChange={vi.fn()} hasLiveSession />);
    expect(screen.getByTestId("live-dot")).toBeInTheDocument();
  });

  it("hides green dot when live tab is active", () => {
    render(<MobileBottomNav activeTab="live" onTabChange={vi.fn()} hasLiveSession />);
    expect(screen.queryByTestId("live-dot")).not.toBeInTheDocument();
  });

  it("shows file count badge when fileCount > 0", () => {
    render(<MobileBottomNav activeTab="thread" onTabChange={vi.fn()} fileCount={5} />);
    const badge = screen.getByTestId("file-count");
    expect(badge).toBeInTheDocument();
    expect(badge.textContent).toBe("5");
  });

  it("does not show file count badge when fileCount is 0", () => {
    render(<MobileBottomNav activeTab="thread" onTabChange={vi.fn()} fileCount={0} />);
    expect(screen.queryByTestId("file-count")).not.toBeInTheDocument();
  });

  it("live tab uses green color when active", () => {
    render(<MobileBottomNav activeTab="live" onTabChange={vi.fn()} />);
    expect(screen.getByTestId("tab-live").className).toContain("text-success");
    expect(screen.getByTestId("accent-live").className).toContain("bg-success");
  });
});

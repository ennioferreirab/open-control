import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { ViewToggle } from "@/components/ViewToggle";

afterEach(cleanup);

describe("ViewToggle", () => {
  it("renders both options", () => {
    render(<ViewToggle value="thread" onChange={vi.fn()} />);
    expect(screen.getByText("Thread")).toBeInTheDocument();
    expect(screen.getByText("Canvas")).toBeInTheDocument();
  });

  it("calls onChange when clicking inactive option", () => {
    const onChange = vi.fn();
    render(<ViewToggle value="thread" onChange={onChange} />);
    fireEvent.click(screen.getByText("Canvas"));
    expect(onChange).toHaveBeenCalledWith("canvas");
  });

  it("shows active state correctly", () => {
    render(<ViewToggle value="thread" onChange={vi.fn()} />);
    const threadButton = screen.getByText("Thread").closest("button")!;
    const canvasButton = screen.getByText("Canvas").closest("button")!;
    expect(threadButton.className).toContain("bg-primary");
    expect(canvasButton.className).toContain("text-muted-foreground");
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { TaskGroupHeader } from "./TaskGroupHeader";

describe("TaskGroupHeader", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders task title and step count badge", () => {
    render(<TaskGroupHeader taskTitle="Build Execution Plan" stepCount={3} />);

    expect(screen.getByText("Build Execution Plan")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("calls onClick when header is clicked", () => {
    const onClick = vi.fn();
    render(<TaskGroupHeader taskTitle="Build Execution Plan" stepCount={3} onClick={onClick} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: "Open task: Build Execution Plan (3 steps)",
      }),
    );
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("has accessible heading semantics", () => {
    render(<TaskGroupHeader taskTitle="Build Execution Plan" stepCount={3} />);

    expect(
      screen.getByRole("heading", { name: "Build Execution Plan", level: 3 }),
    ).toBeInTheDocument();
  });

  it("supports keyboard activation when interactive", () => {
    const onClick = vi.fn();
    render(<TaskGroupHeader taskTitle="Build Execution Plan" stepCount={3} onClick={onClick} />);

    const button = screen.getByRole("button", {
      name: "Open task: Build Execution Plan (3 steps)",
    });
    fireEvent.keyDown(button, { key: "Enter" });
    fireEvent.keyDown(button, { key: " " });
    expect(onClick).toHaveBeenCalledTimes(2);
  });
});

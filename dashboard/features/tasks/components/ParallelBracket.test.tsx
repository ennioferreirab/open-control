import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ParallelBracket } from "@/features/tasks/components/ParallelBracket";

afterEach(cleanup);

describe("ParallelBracket", () => {
  it("renders children inside bracket", () => {
    render(
      <ParallelBracket>
        <div>Step A</div>
        <div>Step B</div>
      </ParallelBracket>,
    );
    expect(screen.getByText("Step A")).toBeInTheDocument();
    expect(screen.getByText("Step B")).toBeInTheDocument();
  });

  it('shows "Parallel" label', () => {
    render(
      <ParallelBracket>
        <div>Child</div>
      </ParallelBracket>,
    );
    expect(screen.getByText("Parallel")).toBeInTheDocument();
  });
});

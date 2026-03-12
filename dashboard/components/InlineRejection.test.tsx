import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { InlineRejection } from "./InlineRejection";

// Track mutation calls
const mockDeny = vi.fn();
const mockReturn = vi.fn();

// Mock motion/react-client to render plain divs
vi.mock("motion/react-client", () => ({
  div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
    const { initial, animate, exit, transition, ...rest } = props;
    void initial;
    void animate;
    void exit;
    void transition;
    return <div {...rest}>{children}</div>;
  },
}));

vi.mock("@/features/tasks/hooks/useInlineRejectionActions", () => ({
  useInlineRejectionActions: () => ({
    deny: mockDeny,
    returnToLeadAgent: mockReturn,
  }),
}));

const baseProps = {
  taskId: "task1" as never,
  onClose: vi.fn(),
};

describe("InlineRejection", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders textarea and buttons", () => {
    render(<InlineRejection {...baseProps} />);
    expect(screen.getByPlaceholderText("Explain what needs to change...")).toBeInTheDocument();
    expect(screen.getByText("Submit")).toBeInTheDocument();
    expect(screen.getByText("Return to Lead Agent")).toBeInTheDocument();
  });

  it("Submit button is disabled when textarea is empty", () => {
    render(<InlineRejection {...baseProps} />);
    const submitBtn = screen.getByText("Submit");
    expect(submitBtn).toBeDisabled();
  });

  it("Return to Lead Agent button is disabled when textarea is empty", () => {
    render(<InlineRejection {...baseProps} />);
    const returnBtn = screen.getByText("Return to Lead Agent");
    expect(returnBtn).toBeDisabled();
  });

  it("enables Submit button when feedback is entered", () => {
    render(<InlineRejection {...baseProps} />);
    const textarea = screen.getByPlaceholderText("Explain what needs to change...");
    fireEvent.change(textarea, { target: { value: "Fix the colors" } });
    expect(screen.getByText("Submit")).not.toBeDisabled();
  });

  it("calls deny mutation with correct feedback on Submit", async () => {
    mockDeny.mockResolvedValue(undefined);
    render(<InlineRejection {...baseProps} />);
    const textarea = screen.getByPlaceholderText("Explain what needs to change...");
    fireEvent.change(textarea, { target: { value: "Fix the colors" } });
    fireEvent.click(screen.getByText("Submit"));
    await waitFor(() => {
      expect(mockDeny).toHaveBeenCalledWith("Fix the colors");
    });
  });

  it("calls returnToLeadAgent mutation on Return to Lead Agent click", async () => {
    mockReturn.mockResolvedValue(undefined);
    render(<InlineRejection {...baseProps} />);
    const textarea = screen.getByPlaceholderText("Explain what needs to change...");
    fireEvent.change(textarea, { target: { value: "Needs re-routing" } });
    fireEvent.click(screen.getByText("Return to Lead Agent"));
    await waitFor(() => {
      expect(mockReturn).toHaveBeenCalledWith("Needs re-routing");
    });
  });

  it("does not submit when only whitespace is entered", () => {
    render(<InlineRejection {...baseProps} />);
    const textarea = screen.getByPlaceholderText("Explain what needs to change...");
    fireEvent.change(textarea, { target: { value: "   " } });
    expect(screen.getByText("Submit")).toBeDisabled();
  });
});

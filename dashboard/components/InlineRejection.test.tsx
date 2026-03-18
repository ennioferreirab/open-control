import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { InlineRejection } from "./InlineRejection";

// Track mutation calls
const mockDeny = vi.fn();

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
    expect(screen.queryByText("Return to Lead Agent")).not.toBeInTheDocument();
  });

  it("Submit button is disabled when textarea is empty", () => {
    render(<InlineRejection {...baseProps} />);
    const submitBtn = screen.getByText("Submit");
    expect(submitBtn).toBeDisabled();
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

  it("does not submit when only whitespace is entered", () => {
    render(<InlineRejection {...baseProps} />);
    const textarea = screen.getByPlaceholderText("Explain what needs to change...");
    fireEvent.change(textarea, { target: { value: "   " } });
    expect(screen.getByText("Submit")).toBeDisabled();
  });
});

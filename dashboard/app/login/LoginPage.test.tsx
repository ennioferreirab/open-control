import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "./page";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders token input and submit button", () => {
    render(<LoginPage />);

    expect(screen.getByLabelText("Access Token")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign In" })).toBeInTheDocument();
    expect(screen.getByText("Mission Control")).toBeInTheDocument();
    expect(screen.getByText("Enter your access token")).toBeInTheDocument();
  });

  it("redirects to dashboard on correct token", async () => {
    const user = userEvent.setup();
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    } as Response);

    const { container } = render(<LoginPage />);
    const form = within(container);

    await user.type(form.getByLabelText("Access Token"), "correct-token");
    await user.click(form.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/");
    });

    expect(global.fetch).toHaveBeenCalledWith("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: "correct-token" }),
    });
  });

  it("shows error message on incorrect token", async () => {
    const user = userEvent.setup();
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: "Invalid access token" }),
    } as Response);

    const { container } = render(<LoginPage />);
    const form = within(container);

    await user.type(form.getByLabelText("Access Token"), "wrong-token");
    await user.click(form.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(form.getByText("Invalid access token")).toBeInTheDocument();
    });

    expect(pushMock).not.toHaveBeenCalled();
  });

  it("submits form on Enter key", async () => {
    const user = userEvent.setup();
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    } as Response);

    const { container } = render(<LoginPage />);
    const form = within(container);

    const input = form.getByLabelText("Access Token");
    await user.type(input, "test-token{Enter}");

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: "test-token" }),
      });
    });
  });

  it("shows loading state during submission", async () => {
    const user = userEvent.setup();

    let resolvePromise: (value: Response) => void;
    vi.mocked(global.fetch).mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePromise = resolve;
      }),
    );

    const { container } = render(<LoginPage />);
    const form = within(container);

    await user.type(form.getByLabelText("Access Token"), "test-token");
    await user.click(form.getByRole("button", { name: "Sign In" }));

    expect(form.getByText("Authenticating...")).toBeInTheDocument();
    expect(form.getByRole("button")).toBeDisabled();

    resolvePromise!({
      ok: true,
      json: async () => ({ success: true }),
    } as Response);

    await waitFor(() => {
      expect(form.getByText("Sign In")).toBeInTheDocument();
    });
  });
});

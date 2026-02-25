import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { HtmlViewer } from "./HtmlViewer";

// Mock react-syntax-highlighter to avoid JSDOM rendering issues
vi.mock("react-syntax-highlighter", () => ({
  default: ({
    children,
    language,
    showLineNumbers,
  }: {
    children: string;
    language: string;
    showLineNumbers?: boolean;
  }) => (
    <pre
      data-testid="syntax-highlighter"
      data-language={language}
      data-show-line-numbers={showLineNumbers ? "true" : "false"}
    >
      {children}
    </pre>
  ),
}));

vi.mock("react-syntax-highlighter/dist/esm/styles/prism", () => ({
  vscDarkPlus: {},
}));

const SAMPLE_HTML = "<html><body><h1>Hello</h1><script>alert('xss')</script></body></html>";

describe("HtmlViewer", () => {
  afterEach(() => {
    cleanup();
  });

  it('defaults to "Rendered" mode with Rendered button having secondary variant', () => {
    render(<HtmlViewer content={SAMPLE_HTML} />);

    const renderedBtn = screen.getByRole("button", { name: "Rendered" });
    const rawBtn = screen.getByRole("button", { name: "Raw" });

    // In rendered mode, Rendered button has secondary variant class
    expect(renderedBtn.className).toContain("secondary");
    // Raw button should not have secondary variant
    expect(rawBtn.className).not.toContain("secondary");
  });

  it("renders an iframe in rendered mode with srcDoc set to content", () => {
    render(<HtmlViewer content={SAMPLE_HTML} />);

    const iframe = screen.getByTitle("HTML preview");
    expect(iframe.tagName).toBe("IFRAME");
    expect(iframe).toHaveAttribute("srcdoc", SAMPLE_HTML);
  });

  it('renders iframe with sandbox="allow-same-origin" (no allow-scripts)', () => {
    render(<HtmlViewer content={SAMPLE_HTML} />);

    const iframe = screen.getByTitle("HTML preview");
    const sandboxAttr = iframe.getAttribute("sandbox");

    expect(sandboxAttr).toBe("allow-same-origin");
    expect(sandboxAttr).not.toContain("allow-scripts");
  });

  it('iframe has title="HTML preview" for accessibility', () => {
    render(<HtmlViewer content={SAMPLE_HTML} />);

    expect(screen.getByTitle("HTML preview")).toBeInTheDocument();
  });

  it("clicking Raw button switches to raw mode showing SyntaxHighlighter", () => {
    render(<HtmlViewer content={SAMPLE_HTML} />);

    // Iframe should be present initially
    expect(screen.getByTitle("HTML preview")).toBeInTheDocument();

    // Click Raw
    fireEvent.click(screen.getByRole("button", { name: "Raw" }));

    // Iframe should be gone, SyntaxHighlighter should appear
    expect(screen.queryByTitle("HTML preview")).not.toBeInTheDocument();
    const highlighter = screen.getByTestId("syntax-highlighter");
    expect(highlighter).toBeInTheDocument();
  });

  it("SyntaxHighlighter in raw mode receives language='html' and shows content", () => {
    render(<HtmlViewer content={SAMPLE_HTML} />);

    fireEvent.click(screen.getByRole("button", { name: "Raw" }));

    const highlighter = screen.getByTestId("syntax-highlighter");
    expect(highlighter).toHaveAttribute("data-language", "html");
    expect(highlighter.textContent).toBe(SAMPLE_HTML);
  });

  it("SyntaxHighlighter in raw mode has showLineNumbers enabled", () => {
    render(<HtmlViewer content={SAMPLE_HTML} />);

    fireEvent.click(screen.getByRole("button", { name: "Raw" }));

    const highlighter = screen.getByTestId("syntax-highlighter");
    expect(highlighter).toHaveAttribute("data-show-line-numbers", "true");
  });

  it("clicking Rendered button switches back to iframe mode from raw mode", () => {
    render(<HtmlViewer content={SAMPLE_HTML} />);

    // Switch to raw
    fireEvent.click(screen.getByRole("button", { name: "Raw" }));
    expect(screen.queryByTitle("HTML preview")).not.toBeInTheDocument();

    // Switch back to rendered
    fireEvent.click(screen.getByRole("button", { name: "Rendered" }));
    expect(screen.getByTitle("HTML preview")).toBeInTheDocument();
    expect(screen.queryByTestId("syntax-highlighter")).not.toBeInTheDocument();
  });

  it("Raw button has secondary variant class when in raw mode", () => {
    render(<HtmlViewer content={SAMPLE_HTML} />);

    fireEvent.click(screen.getByRole("button", { name: "Raw" }));

    const rawBtn = screen.getByRole("button", { name: "Raw" });
    const renderedBtn = screen.getByRole("button", { name: "Rendered" });

    expect(rawBtn.className).toContain("secondary");
    expect(renderedBtn.className).not.toContain("secondary");
  });

  it("renders without crashing when content is empty string", () => {
    render(<HtmlViewer content="" />);

    const iframe = screen.getByTitle("HTML preview");
    expect(iframe).toBeInTheDocument();
    expect(iframe).toHaveAttribute("srcdoc", "");
  });

  it("toggle state is local per instance — a second viewer instance starts in rendered mode (AC#10)", () => {
    const { unmount } = render(<HtmlViewer content={SAMPLE_HTML} />);

    // Switch first instance to raw mode
    fireEvent.click(screen.getByRole("button", { name: "Raw" }));
    expect(screen.queryByTitle("HTML preview")).not.toBeInTheDocument();

    // Unmount first instance, mount a fresh second instance
    unmount();
    render(<HtmlViewer content={SAMPLE_HTML} />);

    // New instance should default to rendered mode
    expect(screen.getByTitle("HTML preview")).toBeInTheDocument();
    expect(screen.queryByTestId("syntax-highlighter")).not.toBeInTheDocument();
  });
});

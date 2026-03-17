import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MarkdownViewer } from "./MarkdownViewer";
import type { ComponentProps } from "react";

type MarkdownViewerProps = ComponentProps<typeof MarkdownViewer>;

// Mock react-syntax-highlighter to avoid JSDOM rendering issues
vi.mock("react-syntax-highlighter", () => ({
  default: ({ children, language }: { children: string; language: string }) => (
    <pre data-testid="syntax-highlighter" data-language={language}>
      {children}
    </pre>
  ),
}));

vi.mock("react-syntax-highlighter/dist/esm/styles/prism", () => ({
  vscDarkPlus: {},
}));

const SAMPLE_MARKDOWN = `# Heading One

## Heading Two

### Heading Three

A paragraph with **bold** and *italic* text.

- item one
- item two

1. first
2. second

[A link](https://example.com)

| Col A | Col B |
|-------|-------|
| cell1 | cell2 |

> A blockquote

\`\`\`javascript
const x = 1;
\`\`\`

\`inline code\`
`;

const OUTPUT_SOURCE_FILE = {
  name: "reports/daily/summary.md",
  subfolder: "output",
};

describe("MarkdownViewer", () => {
  afterEach(() => {
    cleanup();
  });

  it('defaults to "Rendered" mode with Rendered button having secondary variant', () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    const renderedBtn = screen.getByRole("button", { name: "Rendered" });
    const rawBtn = screen.getByRole("button", { name: "Raw" });

    expect(renderedBtn.className).toContain("secondary");
    expect(rawBtn.className).not.toContain("secondary");
  });

  it("renders Markdown content in rendered mode (ReactMarkdown output visible)", () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    // ReactMarkdown renders headings as h1/h2/h3 DOM elements
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3 })).toBeInTheDocument();
  });

  it("renders headings at the correct heading levels", () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    expect(screen.getByRole("heading", { level: 1, name: "Heading One" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Heading Two" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Heading Three" })).toBeInTheDocument();
  });

  it("renders links with target='_blank' and rel='noopener noreferrer'", () => {
    render(<MarkdownViewer content="[Visit Example](https://example.com)" />);

    const link = screen.getByRole("link", { name: "Visit Example" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("resolves relative image sources against the current task markdown file", () => {
    render(
      <MarkdownViewer
        {...({
          content: "![Chart](./images/chart.png)",
          taskId: "task_1",
          sourceFile: OUTPUT_SOURCE_FILE,
        } as MarkdownViewerProps)}
      />,
    );

    const image = screen.getByRole("img", { name: "Chart" });
    expect(image).toHaveAttribute(
      "src",
      "/api/tasks/task_1/files/output/reports%2Fdaily%2Fimages%2Fchart.png",
    );
  });

  it("resolves relative links against the current markdown directory", () => {
    render(
      <MarkdownViewer
        {...({
          content: "[Open artifact](../artifact.html)",
          taskId: "task_1",
          sourceFile: OUTPUT_SOURCE_FILE,
        } as MarkdownViewerProps)}
      />,
    );

    const link = screen.getByRole("link", { name: "Open artifact" });
    expect(link).toHaveAttribute("href", "/api/tasks/task_1/files/output/reports%2Fartifact.html");
  });

  it("keeps absolute URLs unchanged when rendering links", () => {
    render(
      <MarkdownViewer
        {...({
          content: "[External](https://example.com/manual)",
          taskId: "task_1",
          sourceFile: OUTPUT_SOURCE_FILE,
        } as MarkdownViewerProps)}
      />,
    );

    expect(screen.getByRole("link", { name: "External" })).toHaveAttribute(
      "href",
      "https://example.com/manual",
    );
  });

  it("renders a table with table, thead, th, and td elements", () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    const table = screen.getByRole("table");
    expect(table).toBeInTheDocument();

    // Check for column headers
    expect(screen.getByRole("columnheader", { name: "Col A" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Col B" })).toBeInTheDocument();

    // Check for cell data
    expect(screen.getByRole("cell", { name: "cell1" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "cell2" })).toBeInTheDocument();
  });

  it("applies border styling classes to table header cells", () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    const th = screen.getByRole("columnheader", { name: "Col A" });
    expect(th.className).toContain("border-b");
    expect(th.className).toContain("border-border");
  });

  it("applies border styling classes to table data cells", () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    const td = screen.getByRole("cell", { name: "cell1" });
    expect(td.className).toContain("border-b");
    expect(td.className).toContain("border-border");
  });

  it("renders fenced code blocks with SyntaxHighlighter", () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    const highlighter = screen.getByTestId("syntax-highlighter");
    expect(highlighter).toBeInTheDocument();
    expect(highlighter).toHaveAttribute("data-language", "javascript");
    expect(highlighter.textContent).toContain("const x = 1;");
  });

  it("renders inline code without SyntaxHighlighter", () => {
    render(<MarkdownViewer content="`inline code`" />);

    // There should be no SyntaxHighlighter (no language class on inline code)
    expect(screen.queryByTestId("syntax-highlighter")).not.toBeInTheDocument();

    // The inline code should appear as a <code> element
    const codeEl = document.querySelector("code");
    expect(codeEl).toBeTruthy();
    expect(codeEl?.textContent).toBe("inline code");
  });

  it("clicking Raw button switches to raw mode showing pre element with monospace font", () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    fireEvent.click(screen.getByRole("button", { name: "Raw" }));

    // In raw mode, no heading rendered by ReactMarkdown
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();

    // A <pre> element should exist with the raw markdown text
    const pre = document.querySelector("pre.font-mono");
    expect(pre).toBeTruthy();
    expect(pre?.textContent).toBe(SAMPLE_MARKDOWN);
  });

  it("raw mode pre element has whitespace-pre-wrap class", () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    fireEvent.click(screen.getByRole("button", { name: "Raw" }));

    // Select the raw mode pre specifically (not the mocked SyntaxHighlighter pre)
    const pre = document.querySelector("pre.font-mono");
    expect(pre?.className).toContain("whitespace-pre-wrap");
    expect(pre?.className).toContain("font-mono");
  });

  it("raw mode shows the exact source text without rendering", () => {
    const rawText = "# Not Rendered\n\n**bold** text";
    render(<MarkdownViewer content={rawText} />);

    fireEvent.click(screen.getByRole("button", { name: "Raw" }));

    // The raw text should be directly in the pre element
    const pre = document.querySelector("pre.font-mono");
    expect(pre?.textContent).toBe(rawText);

    // Headings should not be rendered as DOM elements
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });

  it("clicking Rendered button switches back to rendered mode from raw mode", () => {
    render(<MarkdownViewer content="# Hello" />);

    // Go to raw
    fireEvent.click(screen.getByRole("button", { name: "Raw" }));
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();

    // Go back to rendered
    fireEvent.click(screen.getByRole("button", { name: "Rendered" }));
    expect(screen.getByRole("heading", { level: 1, name: "Hello" })).toBeInTheDocument();
    expect(document.querySelector("pre.font-mono")).toBeNull();
  });

  it("Raw button has secondary variant class when in raw mode", () => {
    render(<MarkdownViewer content={SAMPLE_MARKDOWN} />);

    fireEvent.click(screen.getByRole("button", { name: "Raw" }));

    const rawBtn = screen.getByRole("button", { name: "Raw" });
    const renderedBtn = screen.getByRole("button", { name: "Rendered" });

    expect(rawBtn.className).toContain("secondary");
    expect(renderedBtn.className).not.toContain("secondary");
  });

  it("renders blockquote element from Markdown", () => {
    render(<MarkdownViewer content="> A blockquote here" />);

    const blockquote = document.querySelector("blockquote");
    expect(blockquote).toBeTruthy();
    expect(blockquote?.className).toContain("border-l-4");
  });

  it("renders unordered list items (AC#6)", () => {
    render(<MarkdownViewer content={"- item one\n- item two"} />);

    const list = document.querySelector("ul");
    expect(list).toBeTruthy();
    expect(list?.className).toContain("list-disc");
    expect(screen.getByText("item one")).toBeInTheDocument();
    expect(screen.getByText("item two")).toBeInTheDocument();
  });

  it("renders ordered list items (AC#6)", () => {
    render(<MarkdownViewer content={"1. first\n2. second"} />);

    const list = document.querySelector("ol");
    expect(list).toBeTruthy();
    expect(list?.className).toContain("list-decimal");
    expect(screen.getByText("first")).toBeInTheDocument();
    expect(screen.getByText("second")).toBeInTheDocument();
  });

  it("renders horizontal rule (AC#6)", () => {
    render(<MarkdownViewer content={"above\n\n---\n\nbelow"} />);

    const hr = document.querySelector("hr");
    expect(hr).toBeTruthy();
    expect(hr?.className).toContain("border-border");
  });

  it("renders bold text (AC#6)", () => {
    render(<MarkdownViewer content="**bold text**" />);

    const strong = document.querySelector("strong");
    expect(strong).toBeTruthy();
    expect(strong?.textContent).toBe("bold text");
    expect(strong?.className).toContain("font-semibold");
  });

  it("renders italic text (AC#6)", () => {
    render(<MarkdownViewer content="*italic text*" />);

    const em = document.querySelector("em");
    expect(em).toBeTruthy();
    expect(em?.textContent).toBe("italic text");
    expect(em?.className).toContain("italic");
  });

  it("toggle state is local per instance — a second viewer instance starts in rendered mode (AC#10)", () => {
    const { unmount } = render(<MarkdownViewer content="# First" />);

    // Switch first instance to raw
    fireEvent.click(screen.getByRole("button", { name: "Raw" }));
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();

    // Unmount first instance, mount a fresh second instance
    unmount();
    render(<MarkdownViewer content="# Second" />);

    // New instance defaults back to rendered mode
    expect(screen.getByRole("heading", { level: 1, name: "Second" })).toBeInTheDocument();
    expect(document.querySelector("pre.font-mono")).toBeNull();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { MarkdownRenderer } from "./MarkdownRenderer";

vi.mock("react-syntax-highlighter", () => ({
  Prism: ({ children }: { children: React.ReactNode }) => (
    <pre data-testid="syntax-highlighter">{children}</pre>
  ),
}));

vi.mock("react-syntax-highlighter/dist/esm/styles/prism", () => ({
  oneDark: {},
}));

describe("MarkdownRenderer", () => {
  afterEach(() => {
    cleanup();
  });

  it("uses a selectable width-constrained root container", () => {
    const { container } = render(<MarkdownRenderer content="Paragraph text" />);

    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain("w-full");
    expect(root.className).toContain("min-w-0");
    expect(root.className).toContain("max-w-full");
    expect(root.className).toContain("select-text");
  });
});

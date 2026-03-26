import { describe, expect, it } from "vitest";
import { linkifyFilePaths } from "../filePathLinker";

describe("linkifyFilePaths", () => {
  it("returns text unchanged when validPaths is empty", () => {
    const text = "Output salvo em: output/report.md";
    expect(linkifyFilePaths(text, new Set())).toBe(text);
  });

  it("linkifies a path after a colon", () => {
    const paths = new Set(["output/brand_brief.md"]);
    const input = "Output salvo em: output/brand_brief.md";
    const result = linkifyFilePaths(input, paths);
    expect(result).toBe(
      "Output salvo em: [output/brand_brief.md](artifact://output/brand_brief.md)",
    );
  });

  it("linkifies a bare filename with known extension", () => {
    const paths = new Set(["report.pdf"]);
    const input = "Generated report.pdf successfully";
    const result = linkifyFilePaths(input, paths);
    expect(result).toBe("Generated [report.pdf](artifact://report.pdf) successfully");
  });

  it("linkifies nested paths", () => {
    const paths = new Set(["output/adrenahunters/2026-03-25_DWUw8JSDZ3Q_reel.mp4"]);
    const input = "Created output/adrenahunters/2026-03-25_DWUw8JSDZ3Q_reel.mp4";
    const result = linkifyFilePaths(input, paths);
    expect(result).toContain(
      "[output/adrenahunters/2026-03-25_DWUw8JSDZ3Q_reel.mp4](artifact://output/adrenahunters/2026-03-25_DWUw8JSDZ3Q_reel.mp4)",
    );
  });

  it("linkifies multiple paths in the same text", () => {
    const paths = new Set(["output/a.md", "output/b.json"]);
    const input = "Created output/a.md and output/b.json";
    const result = linkifyFilePaths(input, paths);
    expect(result).toContain("[output/a.md](artifact://output/a.md)");
    expect(result).toContain("[output/b.json](artifact://output/b.json)");
  });

  it("does NOT linkify paths not in validPaths", () => {
    const paths = new Set(["output/exists.md"]);
    const input = "See output/exists.md and output/missing.md";
    const result = linkifyFilePaths(input, paths);
    expect(result).toContain("[output/exists.md]");
    expect(result).not.toContain("[output/missing.md]");
    expect(result).toContain("output/missing.md"); // still plain text
  });

  it("does NOT match version strings", () => {
    const paths = new Set(["v1.2.3"]);
    const input = "Using version v1.2.3";
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("does NOT match IP addresses", () => {
    const paths = new Set(["192.168.1.1"]);
    const input = "Server at 192.168.1.1";
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("does NOT modify text inside backtick code spans", () => {
    const paths = new Set(["output/file.md"]);
    const input = "Run `output/file.md` to see results";
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("does NOT modify text inside double-backtick code spans", () => {
    const paths = new Set(["output/file.md"]);
    const input = "Run ``output/file.md`` to see results";
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("does NOT modify text inside existing markdown links", () => {
    const paths = new Set(["output/file.md"]);
    const input = "See [the report](output/file.md) for details";
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("does NOT modify text inside fenced code blocks", () => {
    const paths = new Set(["output/file.md"]);
    const input = "Example:\n```\noutput/file.md\n```\nEnd.";
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("does NOT match bare filenames with unknown extensions", () => {
    const paths = new Set(["foo.xyz123"]);
    const input = "See foo.xyz123 for details";
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("does NOT linkify paths embedded in bare URLs", () => {
    const paths = new Set(["output/report.md"]);
    const input = "See https://example.com/output/report.md for details";
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("does NOT linkify paths embedded in http URLs", () => {
    const paths = new Set(["docs/guide.pdf"]);
    const input = "Download from http://cdn.example.com/docs/guide.pdf";
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("does NOT match paths with parentheses (excluded by regex character class)", () => {
    const paths = new Set(["output/report(v2).md"]);
    const input = "See output/report(v2).md";
    // Parentheses are not in [\w@.-], so the full path is not matched as a single token
    expect(linkifyFilePaths(input, paths)).toBe(input);
  });

  it("handles file paths at start and end of line", () => {
    const paths = new Set(["output/start.md", "output/end.md"]);
    const input = "output/start.md is the first and last is output/end.md";
    const result = linkifyFilePaths(input, paths);
    expect(result).toContain("[output/start.md](artifact://output/start.md)");
    expect(result).toContain("[output/end.md](artifact://output/end.md)");
  });

  it("linkifies path next to URL without affecting the URL", () => {
    const paths = new Set(["output/report.md"]);
    const input = "See output/report.md and https://example.com/other.md";
    const result = linkifyFilePaths(input, paths);
    expect(result).toContain("[output/report.md](artifact://output/report.md)");
    expect(result).toContain("https://example.com/other.md");
    expect(result).not.toContain("[https://");
  });
});

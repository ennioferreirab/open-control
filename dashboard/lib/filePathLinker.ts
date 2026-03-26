/**
 * Detects file path patterns in text and wraps validated ones as markdown links.
 *
 * Used to make file references in agent message content clickable when they
 * match a known artifact path.
 */

const KNOWN_EXTENSIONS = new Set([
  "md",
  "txt",
  "pdf",
  "csv",
  "json",
  "yaml",
  "yml",
  "py",
  "ts",
  "tsx",
  "js",
  "jsx",
  "html",
  "css",
  "go",
  "rs",
  "java",
  "sh",
  "xml",
  "sql",
  "toml",
  "png",
  "jpg",
  "jpeg",
  "gif",
  "svg",
  "webp",
  "mp4",
  "mp3",
  "wav",
  "zip",
  "tar",
  "gz",
  "doc",
  "docx",
  "xls",
  "xlsx",
  "pptx",
  "log",
  "env",
  "cfg",
  "ini",
]);

// Matches file-path-like strings:
//   - With slashes: output/file.md, path/to/file.ext
//   - Bare filenames: report.pdf (only if extension is in KNOWN_EXTENSIONS)
// Created fresh per call to avoid stateful lastIndex issues with /g flag.
function createFilePathRegex(): RegExp {
  return /(?:[\w@.-]+\/)+[\w@.-]+\.[\w]+|[\w@.-]+\.[\w]+/g;
}

/**
 * Replace file paths in plain text segments with markdown links,
 * skipping code spans, bare URLs, and existing markdown links.
 */
export function linkifyFilePaths(text: string, validPaths: Set<string>): string {
  if (validPaths.size === 0) return text;

  const segments = splitProtectedSegments(text);

  return segments
    .map((seg) => {
      if (seg.protected) return seg.text;
      return replaceFilePathsInText(seg.text, validPaths);
    })
    .join("");
}

interface Segment {
  text: string;
  protected: boolean;
}

/**
 * Split text into protected segments (code spans, fenced code blocks,
 * bare URLs, existing markdown links) and plain text segments.
 */
function splitProtectedSegments(text: string): Segment[] {
  // Match (in order):
  //   1. Fenced code blocks: ```...```
  //   2. Double-backtick code spans: ``...``
  //   3. Single-backtick code spans: `...`
  //   4. Markdown links: [text](url)
  //   5. Bare URLs: http:// or https:// followed by non-whitespace
  const protectedRe = /```[\s\S]*?```|``[^`]*``|`[^`]+`|\[[^\]]*\]\([^)]*\)|https?:\/\/\S+/g;
  const segments: Segment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = protectedRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ text: text.slice(lastIndex, match.index), protected: false });
    }
    segments.push({ text: match[0], protected: true });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    segments.push({ text: text.slice(lastIndex), protected: false });
  }

  return segments;
}

function escapeMarkdownLinkPath(path: string): string {
  return path.replace(/[()]/g, (ch) => `\\${ch}`);
}

/**
 * Replace file path matches in a plain text segment with artifact:// markdown links.
 * Only paths present in validPaths are linkified.
 */
function replaceFilePathsInText(text: string, validPaths: Set<string>): string {
  return text.replace(createFilePathRegex(), (match) => {
    // Skip version strings like v1.2.3
    if (/^v?\d+\.\d+(\.\d+)*$/.test(match)) return match;

    // Skip IP-like patterns: 192.168.1.1
    if (/^\d+\.\d+\.\d+\.\d+$/.test(match)) return match;

    // Extract extension and check if it's known (for bare filenames without slashes)
    const hasSlash = match.includes("/");
    const dotIdx = match.lastIndexOf(".");
    const ext = dotIdx >= 0 ? match.slice(dotIdx + 1).toLowerCase() : "";

    if (!hasSlash && !KNOWN_EXTENSIONS.has(ext)) return match;

    // Only linkify if the path is in the valid set
    if (!validPaths.has(match)) return match;

    return `[${match}](artifact://${escapeMarkdownLinkPath(match)})`;
  });
}

import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { homedir } from "os";
import { join } from "path";

const BOARD_NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

const MIME_MAP: Record<string, string> = {
  pdf: "application/pdf",
  md: "text/markdown; charset=utf-8",
  markdown: "text/markdown; charset=utf-8",
  html: "text/html; charset=utf-8",
  htm: "text/html; charset=utf-8",
  txt: "text/plain; charset=utf-8",
  csv: "text/csv; charset=utf-8",
  json: "application/json; charset=utf-8",
  yaml: "text/yaml; charset=utf-8",
  yml: "text/yaml; charset=utf-8",
  xml: "application/xml; charset=utf-8",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  gif: "image/gif",
  svg: "image/svg+xml",
  webp: "image/webp",
  bmp: "image/bmp",
  ico: "image/x-icon",
  py: "text/x-python; charset=utf-8",
  ts: "text/typescript; charset=utf-8",
  tsx: "text/typescript; charset=utf-8",
  js: "text/javascript; charset=utf-8",
  jsx: "text/javascript; charset=utf-8",
  go: "text/x-go; charset=utf-8",
  rs: "text/x-rust; charset=utf-8",
  java: "text/x-java; charset=utf-8",
  sh: "text/x-sh; charset=utf-8",
  bash: "text/x-sh; charset=utf-8",
  zsh: "text/x-sh; charset=utf-8",
  css: "text/css; charset=utf-8",
  scss: "text/x-scss; charset=utf-8",
  sql: "text/x-sql; charset=utf-8",
  log: "text/plain; charset=utf-8",
};

function getMimeType(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return MIME_MAP[ext] ?? "application/octet-stream";
}

function isValidPath(segments: string[]): boolean {
  return (
    segments.length > 0 &&
    segments.every(
      (segment) =>
        segment.length > 0 && segment !== "." && segment !== ".." && !segment.includes("\\"),
    )
  );
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ boardName: string; path: string[] }> },
) {
  const { boardName, path } = await params;

  if (!BOARD_NAME_RE.test(boardName)) {
    return NextResponse.json({ error: "Invalid boardName" }, { status: 400 });
  }
  if (!isValidPath(path)) {
    return NextResponse.json({ error: "Invalid path" }, { status: 400 });
  }

  const relativePath = path.join("/");
  const filePath = join(homedir(), ".nanobot", "boards", boardName, "artifacts", relativePath);

  let buffer: Buffer;
  try {
    buffer = await readFile(filePath);
  } catch (error: unknown) {
    const isNotFound =
      error &&
      typeof error === "object" &&
      "code" in error &&
      (error as { code: string }).code === "ENOENT";
    if (isNotFound) {
      return NextResponse.json({ error: "File not found" }, { status: 404 });
    }
    return NextResponse.json({ error: "Failed to read file" }, { status: 500 });
  }

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": getMimeType(relativePath),
      "Content-Disposition": `inline; filename="${encodeURIComponent(path[path.length - 1] ?? "artifact")}"`,
      "Content-Length": String(buffer.length),
      "Cache-Control": "private, max-age=60",
    },
  });
}

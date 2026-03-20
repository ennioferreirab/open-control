import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { getRuntimePath } from "@/lib/runtimeHome";

const TASK_ID_RE = /^[a-zA-Z0-9_-]+$/;
const VALID_SUBFOLDERS = new Set(["attachments", "output"]);
const FILENAME_RE = /^[^/\\]+$/; // no path separators

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

function isValidFilename(subfolder: string, filename: string): boolean {
  if (subfolder === "attachments") {
    return FILENAME_RE.test(filename) && filename !== "..";
  }

  if (subfolder !== "output" || !filename || filename.startsWith("/") || filename.includes("\\")) {
    return false;
  }

  return filename
    .split("/")
    .every((segment) => segment.length > 0 && segment !== "." && segment !== "..");
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ taskId: string; subfolder: string; filename: string }> },
) {
  const { taskId, subfolder, filename } = await params;

  if (!TASK_ID_RE.test(taskId)) {
    return NextResponse.json({ error: "Invalid taskId" }, { status: 400 });
  }
  if (!VALID_SUBFOLDERS.has(subfolder)) {
    return NextResponse.json({ error: "Invalid subfolder" }, { status: 400 });
  }
  if (!isValidFilename(subfolder, filename)) {
    return NextResponse.json({ error: "Invalid filename" }, { status: 400 });
  }

  const filePath = getRuntimePath("tasks", taskId, subfolder, filename);

  let buffer: Buffer;
  try {
    buffer = await readFile(filePath);
  } catch (err: unknown) {
    const isNotFound =
      err &&
      typeof err === "object" &&
      "code" in err &&
      (err as { code: string }).code === "ENOENT";
    if (isNotFound) {
      return NextResponse.json({ error: "File not found" }, { status: 404 });
    }
    return NextResponse.json({ error: "Failed to read file" }, { status: 500 });
  }

  const contentType = getMimeType(filename);
  const encodedFilename = encodeURIComponent(filename);

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": `inline; filename="${encodedFilename}"`,
      "Content-Length": String(buffer.length),
      "Cache-Control": "private, max-age=60",
    },
  });
}

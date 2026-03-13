import { NextRequest, NextResponse } from "next/server";
import { mkdir, readdir, rename, rm, stat, writeFile } from "fs/promises";
import { homedir } from "os";
import { basename, join } from "path";

const BOARD_NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

const MIME_MAP: Record<string, string> = {
  md: "text/markdown",
  markdown: "text/markdown",
  txt: "text/plain",
  json: "application/json",
  html: "text/html",
  htm: "text/html",
  pdf: "application/pdf",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  svg: "image/svg+xml",
};

function getMimeType(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return MIME_MAP[ext] ?? "application/octet-stream";
}

async function listArtifacts(
  dir: string,
  prefix = "",
): Promise<Array<{ name: string; path: string; size: number; type: string }>> {
  const entries = await readdir(dir, { withFileTypes: true });
  const files: Array<{ name: string; path: string; size: number; type: string }> = [];

  for (const entry of entries) {
    const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name;
    const absolutePath = join(dir, entry.name);

    if (entry.isDirectory()) {
      files.push(...(await listArtifacts(absolutePath, relativePath)));
      continue;
    }

    if (!entry.isFile()) {
      continue;
    }

    const fileStat = await stat(absolutePath);
    files.push({
      name: entry.name,
      path: relativePath,
      size: fileStat.size,
      type: getMimeType(entry.name),
    });
  }

  return files.sort((a, b) => a.path.localeCompare(b.path));
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ boardName: string }> },
) {
  const { boardName } = await params;

  if (!BOARD_NAME_RE.test(boardName)) {
    return NextResponse.json({ error: "Invalid boardName" }, { status: 400 });
  }

  const artifactsDir = join(homedir(), ".nanobot", "boards", boardName, "artifacts");

  try {
    const files = await listArtifacts(artifactsDir);
    return NextResponse.json(files);
  } catch (error: unknown) {
    const isNotFound =
      error &&
      typeof error === "object" &&
      "code" in error &&
      (error as { code: string }).code === "ENOENT";
    if (isNotFound) {
      return NextResponse.json([]);
    }
    return NextResponse.json({ error: "Failed to list artifacts" }, { status: 500 });
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ boardName: string }> },
) {
  const { boardName } = await params;

  if (!BOARD_NAME_RE.test(boardName)) {
    return NextResponse.json({ error: "Invalid boardName" }, { status: 400 });
  }

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json({ error: "Failed to parse multipart form data" }, { status: 400 });
  }

  const artifactsDir = join(homedir(), ".nanobot", "boards", boardName, "artifacts");
  await mkdir(artifactsDir, { recursive: true });

  const uploadedFiles: Array<{ name: string; path: string; size: number; type: string }> = [];

  for (const [, value] of formData.entries()) {
    if (!(value instanceof File)) {
      continue;
    }

    const file = value;
    if (file.size > MAX_FILE_SIZE) {
      return NextResponse.json(
        { error: `File "${file.name}" exceeds 10MB limit` },
        { status: 413 },
      );
    }

    const safeName = basename(file.name);
    if (!safeName) {
      continue;
    }

    const finalPath = join(artifactsDir, safeName);
    const tmpPath = `${finalPath}.tmp`;
    const buffer = Buffer.from(await file.arrayBuffer());

    try {
      await writeFile(tmpPath, buffer);
      await rename(tmpPath, finalPath);
    } catch {
      await rm(tmpPath, { force: true });
      return NextResponse.json({ error: `Failed to write file: ${safeName}` }, { status: 500 });
    }

    uploadedFiles.push({
      name: safeName,
      path: safeName,
      size: file.size,
      type: file.type || getMimeType(safeName),
    });
  }

  return NextResponse.json({ files: uploadedFiles });
}

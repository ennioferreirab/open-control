import { NextRequest, NextResponse } from "next/server";
import { readFile, readdir, writeFile, mkdir } from "fs/promises";
import { join, dirname } from "path";
import { homedir } from "os";

const AGENT_NAME_RE = /^[a-zA-Z0-9_-]+$/;
const ALLOWED_FILENAMES = new Set(["MEMORY.md", "HISTORY.md"]);

async function tryReadFile(filePath: string): Promise<string | null> {
  try {
    const content = await readFile(filePath, "utf-8");
    return content.trim() ? content : null;
  } catch {
    return null;
  }
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await readFile(filePath);
    return true;
  } catch {
    return false;
  }
}

async function resolvePaths(
  nanobotDir: string,
  agentName: string,
  filename: string,
): Promise<{ readPath: string | null; writePath: string }> {
  const globalPath = join(nanobotDir, "agents", agentName, "memory", filename);

  try {
    const boardsDir = join(nanobotDir, "boards");
    const boards = await readdir(boardsDir);
    for (const board of boards) {
      if (!AGENT_NAME_RE.test(board)) continue;
      const boardPath = join(boardsDir, board, "agents", agentName, "memory", filename);
      if (await fileExists(boardPath)) {
        return { readPath: boardPath, writePath: boardPath };
      }
    }
  } catch {
    // boards dir doesn't exist
  }

  return { readPath: (await fileExists(globalPath)) ? globalPath : null, writePath: globalPath };
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ agentName: string; filename: string }> },
) {
  const { agentName, filename } = await params;

  if (!AGENT_NAME_RE.test(agentName)) {
    return NextResponse.json({ error: "Invalid agentName" }, { status: 400 });
  }
  if (!ALLOWED_FILENAMES.has(filename)) {
    return NextResponse.json({ error: "Invalid filename" }, { status: 400 });
  }

  const nanobotDir = join(homedir(), ".nanobot");
  const { readPath } = await resolvePaths(nanobotDir, agentName, filename);

  if (!readPath) {
    return NextResponse.json({ error: "File not found" }, { status: 404 });
  }

  const content = await tryReadFile(readPath);
  if (content === null) {
    return NextResponse.json({ error: "File not found" }, { status: 404 });
  }

  return new NextResponse(content, {
    status: 200,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ agentName: string; filename: string }> },
) {
  const { agentName, filename } = await params;

  if (!AGENT_NAME_RE.test(agentName)) {
    return NextResponse.json({ error: "Invalid agentName" }, { status: 400 });
  }
  if (!ALLOWED_FILENAMES.has(filename)) {
    return NextResponse.json({ error: "Invalid filename" }, { status: 400 });
  }

  const body = await request.text();
  const nanobotDir = join(homedir(), ".nanobot");
  const { writePath } = await resolvePaths(nanobotDir, agentName, filename);

  try {
    await mkdir(dirname(writePath), { recursive: true });
    await writeFile(writePath, body, "utf-8");
    return new NextResponse(null, { status: 204 });
  } catch {
    return NextResponse.json({ error: "Failed to write file" }, { status: 500 });
  }
}

import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { join } from "path";
import { homedir } from "os";

const AGENT_NAME_RE = /^[a-zA-Z0-9_-]+$/;
const ALLOWED_FILENAMES = new Set(["MEMORY.md", "HISTORY.md"]);

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

  const filePath = join(homedir(), ".nanobot", "agents", agentName, "memory", filename);

  try {
    const content = await readFile(filePath, "utf-8");
    return new NextResponse(content, {
      status: 200,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  } catch (err: unknown) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return NextResponse.json({ error: "File not found" }, { status: 404 });
    }
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}

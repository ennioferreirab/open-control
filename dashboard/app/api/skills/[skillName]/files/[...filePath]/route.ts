import { NextRequest, NextResponse } from "next/server";
import { readFile, writeFile, mkdir } from "fs/promises";
import { join, dirname, normalize } from "path";
import { homedir } from "os";

const SKILL_NAME_RE = /^[a-zA-Z0-9_-]+$/;

function skillsDir(): string {
  return join(homedir(), ".nanobot", "workspace", "skills");
}

function resolveSkillFilePath(skillName: string, filePath: string[]): string | null {
  const base = join(skillsDir(), skillName);
  const resolved = normalize(join(base, ...filePath));
  // Prevent path traversal
  if (!resolved.startsWith(base)) return null;
  return resolved;
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ skillName: string; filePath: string[] }> },
) {
  const { skillName, filePath } = await params;

  if (!SKILL_NAME_RE.test(skillName)) {
    return NextResponse.json({ error: "Invalid skill name" }, { status: 400 });
  }

  const resolved = resolveSkillFilePath(skillName, filePath);
  if (!resolved) {
    return NextResponse.json({ error: "Invalid file path" }, { status: 400 });
  }

  try {
    const content = await readFile(resolved, "utf-8");
    return NextResponse.json({ content });
  } catch {
    return NextResponse.json({ error: "File not found" }, { status: 404 });
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ skillName: string; filePath: string[] }> },
) {
  const { skillName, filePath } = await params;

  if (!SKILL_NAME_RE.test(skillName)) {
    return NextResponse.json({ error: "Invalid skill name" }, { status: 400 });
  }

  const resolved = resolveSkillFilePath(skillName, filePath);
  if (!resolved) {
    return NextResponse.json({ error: "Invalid file path" }, { status: 400 });
  }

  let body: { content: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (typeof body.content !== "string") {
    return NextResponse.json({ error: "Missing content field" }, { status: 400 });
  }

  try {
    await mkdir(dirname(resolved), { recursive: true });
    await writeFile(resolved, body.content, "utf-8");
    return new NextResponse(null, { status: 204 });
  } catch {
    return NextResponse.json({ error: "Failed to write file" }, { status: 500 });
  }
}

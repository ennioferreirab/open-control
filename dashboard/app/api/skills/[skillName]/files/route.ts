import { NextRequest, NextResponse } from "next/server";
import { readdir, lstat } from "fs/promises";
import { join, extname } from "path";
import { getRuntimePath } from "@/lib/runtimeHome";

const SKILL_NAME_RE = /^[a-zA-Z0-9_-]+$/;
const MAX_DEPTH = 5;

/** Extensions considered safe to read as UTF-8 text. */
const TEXT_EXTENSIONS = new Set([
  ".md", ".txt", ".yaml", ".yml", ".json", ".toml",
  ".py", ".ts", ".js", ".tsx", ".jsx", ".sh", ".bash",
  ".xml", ".html", ".css", ".csv", ".env", ".cfg", ".ini", ".conf",
  "",  // extensionless files (e.g. Makefile, Dockerfile)
]);

function skillsDir(): string {
  return getRuntimePath("workspace", "skills");
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ skillName: string }> },
) {
  const { skillName } = await params;

  if (!SKILL_NAME_RE.test(skillName)) {
    return NextResponse.json({ error: "Invalid skill name" }, { status: 400 });
  }

  const skillDir = join(skillsDir(), skillName);

  try {
    const files = await listFilesRecursive(skillDir, "", 0);
    return NextResponse.json({ files });
  } catch {
    return NextResponse.json({ error: "Skill directory not found" }, { status: 404 });
  }
}

async function listFilesRecursive(
  base: string,
  rel: string,
  depth: number,
): Promise<{ path: string; isDirectory: boolean }[]> {
  if (depth > MAX_DEPTH) return [];

  const entries = await readdir(join(base, rel), { withFileTypes: true });
  const result: { path: string; isDirectory: boolean }[] = [];

  for (const entry of entries) {
    const entryRel = rel ? `${rel}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      result.push({ path: entryRel, isDirectory: true });
      const children = await listFilesRecursive(base, entryRel, depth + 1);
      result.push(...children);
    } else {
      try {
        const info = await lstat(join(base, entryRel));
        // Skip symlinks, binary files, and files larger than 1MB
        if (info.isSymbolicLink() || info.size > 1_048_576) continue;
        if (!TEXT_EXTENSIONS.has(extname(entry.name).toLowerCase())) continue;
        result.push({ path: entryRel, isDirectory: false });
      } catch {
        // Skip entries that can't be stat'd (broken symlinks, permission issues)
      }
    }
  }

  return result;
}

import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { getRuntimePath } from "@/lib/runtimeHome";

/**
 * Write a SKILL.md file to the runtime workspace on disk.
 *
 * Creates `~/.nanobot/workspace/skills/<name>/SKILL.md` with YAML frontmatter.
 * Called before the Convex mutation so failures are caught early.
 */
export function writeSkillToDisk(
  name: string,
  description: string,
  content: string,
  options?: { always?: boolean; metadata?: string },
): void {
  const skillDir = getRuntimePath("workspace", "skills", name);
  mkdirSync(skillDir, { recursive: true });

  const frontmatterLines = [
    "---",
    `name: ${name}`,
    `description: "${description.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`,
  ];
  if (options?.always) {
    frontmatterLines.push("always: true");
  }
  if (options?.metadata) {
    frontmatterLines.push(`metadata: ${options.metadata}`);
  }
  frontmatterLines.push("---", "");

  const skillMdContent = frontmatterLines.join("\n") + "\n" + content + "\n";
  writeFileSync(join(skillDir, "SKILL.md"), skillMdContent, "utf-8");
}

/**
 * Delete a skill directory from the runtime workspace on disk.
 * Best-effort — does not throw if the directory doesn't exist.
 */
export function deleteSkillFromDisk(name: string): void {
  try {
    const skillDir = getRuntimePath("workspace", "skills", name);
    rmSync(skillDir, { recursive: true, force: true });
  } catch {
    // Best-effort cleanup
  }
}

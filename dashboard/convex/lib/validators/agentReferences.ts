import { ConvexError } from "convex/values";

/**
 * Minimal db accessor subset needed by agent reference validators.
 * Defined as a structural interface so both the real Convex DatabaseReader
 * and lightweight unit-test mocks satisfy it.
 */
export interface SkillValidatorDb {
  query(table: string): {
    withIndex(
      index: string,
      cb: (q: { eq(k: string, v: unknown): unknown }) => unknown,
    ): { unique(): Promise<Record<string, unknown> | null> };
  };
}

/**
 * Validates that all skill names referenced by an agent exist in the skills table
 * and are available for use.
 *
 * @param ctx - DB context with read access
 * @param skillNames - Array of skill name strings to validate
 * @param agentName - Agent name for error messages
 */
export async function validateSkillReferences(
  ctx: { db: SkillValidatorDb },
  skillNames: string[],
  agentName: string,
): Promise<void> {
  for (const skillName of skillNames) {
    const skill = await ctx.db
      .query("skills")
      .withIndex("by_name", (q) => q.eq("name", skillName))
      .unique();
    if (!skill || skill.available === false) {
      throw new ConvexError(
        `Agent "${agentName}" references skill "${skillName}" which does not exist or is unavailable`,
      );
    }
  }
}

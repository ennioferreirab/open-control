import { internalMutation } from "./_generated/server";

/**
 * One-shot migration: convert all tasks with trustLevel "agent_reviewed"
 * to "human_approved". Run once via Convex dashboard, then delete this file.
 */
export const migrateAgentReviewedToHumanApproved = internalMutation({
  args: {},
  handler: async (ctx) => {
    const tasks = await ctx.db.query("tasks").collect();
    let count = 0;
    for (const task of tasks) {
      if ((task as any).trustLevel === "agent_reviewed") {
        await ctx.db.patch(task._id, { trustLevel: "human_approved" as any });
        count++;
      }
    }
    return { migrated: count };
  },
});

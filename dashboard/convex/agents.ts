import { internalMutation, mutation, query } from "./_generated/server";
import { ConvexError, v } from "convex/values";

import { agentStatusValidator, interactiveProviderValidator } from "./schema";
import { validateSkillReferences } from "./lib/validators/agentReferences";

const LEGACY_LEAD_AGENT_NAME = "lead-agent";
const ORCHESTRATOR_AGENT_NAME = "orchestrator-agent";
const ORCHESTRATOR_AGENT_DISPLAY_NAME = "Orchestrator Agent";
const ORCHESTRATOR_AGENT_ROLE = "Orchestrator Agent";

function replaceLegacyText(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  return value
    .replaceAll("lead_agent_chat", "orchestrator_agent_chat")
    .replaceAll("lead_agent", "orchestrator_agent")
    .replaceAll("lead-agent", "orchestrator-agent")
    .replaceAll("Lead Agent", ORCHESTRATOR_AGENT_DISPLAY_NAME)
    .replaceAll("lead agent", ORCHESTRATOR_AGENT_DISPLAY_NAME)
    .replaceAll("Lead Orchestrator", ORCHESTRATOR_AGENT_ROLE)
    .replaceAll("Orchestrator Agent — Orchestrator", ORCHESTRATOR_AGENT_ROLE)
    .replaceAll("Orchestrator Agent -- Orchestrator", ORCHESTRATOR_AGENT_ROLE);
}

function normalizeAgentDisplayName(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const nextValue = replaceLegacyText(value);
  return nextValue === undefined ? undefined : nextValue;
}

function normalizeAgentRole(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const nextValue = replaceLegacyText(value);
  return nextValue === undefined ? undefined : nextValue;
}

function replaceLegacyAgentName(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  return value === LEGACY_LEAD_AGENT_NAME ? ORCHESTRATOR_AGENT_NAME : value;
}

function replaceLegacyRoutingMode(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  return value === "lead_agent" ? "orchestrator_agent" : value;
}

function replaceLegacyThreadType(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  return value === "lead_agent_chat" ? "orchestrator_agent_chat" : value;
}

function replaceLegacyStringArray(values: string[] | undefined): string[] | undefined {
  if (!Array.isArray(values)) return undefined;
  const updated = values.map((value) => replaceLegacyAgentName(value) ?? value);
  return updated.some((value, index) => value !== values[index]) ? updated : undefined;
}

function normalizeExecutionPlan(
  plan: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  if (!plan || typeof plan !== "object") return undefined;
  let changed = false;
  const nextPlan: Record<string, unknown> = { ...plan };

  if (plan.generatedBy === LEGACY_LEAD_AGENT_NAME) {
    nextPlan.generatedBy = ORCHESTRATOR_AGENT_NAME;
    changed = true;
  }

  if (Array.isArray(plan.steps)) {
    const updatedSteps = plan.steps.map((step) => {
      if (!step || typeof step !== "object") return step;
      const stepRecord = step as Record<string, unknown>;
      if (stepRecord.assignedAgent !== LEGACY_LEAD_AGENT_NAME) {
        return step;
      }
      changed = true;
      return {
        ...stepRecord,
        assignedAgent: ORCHESTRATOR_AGENT_NAME,
      };
    });
    if (changed) {
      nextPlan.steps = updatedSteps;
    }
  }

  return changed ? nextPlan : undefined;
}

// ---------------------------------------------------------------------------
// Agent metric helpers — callable from lifecycle completion paths
// ---------------------------------------------------------------------------

/**
 * Minimal db accessor subset needed by agent metric helpers.
 * Defined as a structural interface (method shorthand) so both the real
 * Convex DatabaseWriter and lightweight unit-test mocks satisfy it.
 */
export interface AgentMetricDb {
  query(table: string): {
    withIndex(
      index: string,
      cb: (q: { eq(k: string, v: unknown): unknown }) => unknown,
    ): { first(): Promise<Record<string, unknown> | null> };
  };
  patch(id: unknown, value: Record<string, unknown>): Promise<void>;
}

export async function incrementAgentTaskMetric(
  db: AgentMetricDb,
  agentName: string,
): Promise<void> {
  const agent = await db
    .query("agents")
    .withIndex("by_name", (q: { eq: (k: string, v: string) => unknown }) => q.eq("name", agentName))
    .first();
  if (!agent) return;
  const id = agent._id as string;
  const current = (agent.tasksExecuted as number | undefined) ?? 0;
  await db.patch(id, {
    tasksExecuted: current + 1,
    lastTaskExecutedAt: new Date().toISOString(),
  });
}

export async function incrementAgentStepMetric(
  db: AgentMetricDb,
  agentName: string,
): Promise<void> {
  const agent = await db
    .query("agents")
    .withIndex("by_name", (q: { eq: (k: string, v: string) => unknown }) => q.eq("name", agentName))
    .first();
  if (!agent) return;
  const id = agent._id as string;
  const current = (agent.stepsExecuted as number | undefined) ?? 0;
  await db.patch(id, {
    stepsExecuted: current + 1,
    lastStepExecutedAt: new Date().toISOString(),
  });
}

export const list = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("agents").collect();
    return all.filter((a) => !a.deletedAt);
  },
});

// Roles that represent runtime-only surfaces, not task-delegatable agents.
const NON_DELEGATABLE_ROLES = new Set(["remote-terminal", "terminal", "system-terminal"]);

export const listActiveRegistryView = query({
  args: {},
  handler: async (ctx) => {
    const allAgents = await ctx.db.query("agents").collect();
    // Filter: not deleted, not system, enabled, and delegatable role
    const active = allAgents.filter(
      (a) =>
        !a.deletedAt && !a.isSystem && a.enabled !== false && !NON_DELEGATABLE_ROLES.has(a.role),
    );

    // Resolve squad memberships
    const allSquadSpecs = await ctx.db
      .query("squadSpecs")
      .withIndex("by_status", (q) => q.eq("status", "published"))
      .collect();

    return active.map((agent) => {
      const squads = allSquadSpecs
        .filter((s) => {
          const agentIds = (s.agentIds ?? []) as string[];
          return agentIds.includes(String(agent._id));
        })
        .map((s) => ({ id: s._id, name: s.name, displayName: s.displayName }));

      return {
        agentId: agent._id,
        name: agent.name,
        displayName: agent.displayName,
        role: agent.role,
        skills: agent.skills,
        squads,
        enabled: agent.enabled ?? true,
        status: agent.status,
        tasksExecuted: agent.tasksExecuted ?? 0,
        stepsExecuted: agent.stepsExecuted ?? 0,
        lastTaskExecutedAt: agent.lastTaskExecutedAt ?? null,
        lastStepExecutedAt: agent.lastStepExecutedAt ?? null,
        lastActiveAt: agent.lastActiveAt ?? null,
      };
    });
  },
});

export const upsertByName = mutation({
  args: {
    name: v.string(),
    displayName: v.optional(v.string()),
    role: v.string(),
    prompt: v.optional(v.string()),
    soul: v.optional(v.string()),
    skills: v.array(v.string()),
    model: v.optional(v.string()),
    interactiveProvider: v.optional(interactiveProviderValidator),
    claudeCodeOpts: v.optional(
      v.object({
        permissionMode: v.optional(v.string()),
        maxBudgetUsd: v.optional(v.number()),
        maxTurns: v.optional(v.number()),
      }),
    ),
    isSystem: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    // NOTE: skill validation is intentionally skipped in upsertByName.
    // This is the internal agent-sync path called at boot from YAML configs.
    // Agents may reference skills registered through squad definitions that aren't
    // in the global skills table. Validation happens at squad graph publication time.

    const existing = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();

    const timestamp = new Date().toISOString();

    if (existing) {
      // Defense-in-depth: skip upsert for soft-deleted agents.
      // The YAML should have been cleaned up by sync; this guards against manual recreation.
      if (existing.deletedAt) {
        // Agent is soft-deleted; skip re-registration. Log for operator visibility.
        console.warn(
          `[agents:upsertByName] Skipped upsert for deleted agent '${args.name}' — YAML should be cleaned up by sync.`,
        );
        return;
      }
      // Convex is source of truth for prompt, variables, and skills edited in
      // the dashboard. Startup YAML sync should only refresh identity/model.
      const patch: Record<string, unknown> = {
        displayName: args.displayName ?? undefined,
        role: args.role,
        model: args.model,
        interactiveProvider: args.interactiveProvider,
        lastActiveAt: timestamp,
        // Preserve existing enabled value on update (don't reset on re-sync)
      };
      // When the agent has a compiled projection, prompt and soul are
      // authoritative from the spec compiler — never overwrite them from YAML.
      if (!existing.compiledFromSpecId) {
        // Set prompt only if agent has none yet (first-time bootstrap)
        if (!existing.prompt && args.prompt) {
          patch.prompt = args.prompt;
        }
        // Set soul from YAML only for non-compiled agents.
        if (args.soul !== undefined) {
          patch.soul = args.soul;
        }
      }
      // Bootstrap skills from YAML only when the existing document has no
      // skills yet. After that, dashboard edits remain authoritative.
      if (
        (!Array.isArray(existing.skills) || existing.skills.length === 0) &&
        args.skills.length > 0
      ) {
        patch.skills = args.skills;
      }
      if (args.isSystem !== undefined) {
        patch.isSystem = args.isSystem;
      }
      if (args.interactiveProvider !== undefined) {
        patch.interactiveProvider = args.interactiveProvider;
      }
      if (args.claudeCodeOpts !== undefined) {
        patch.claudeCodeOpts = args.claudeCodeOpts;
      }
      await ctx.db.patch(existing._id, patch);
    } else {
      await ctx.db.insert("agents", {
        name: args.name,
        displayName: args.displayName ?? undefined,
        role: args.role,
        prompt: args.prompt,
        soul: args.soul,
        skills: args.skills,
        status: "idle",
        enabled: true,
        isSystem: args.isSystem,
        model: args.model,
        interactiveProvider: args.interactiveProvider,
        claudeCodeOpts: args.claudeCodeOpts,
        lastActiveAt: timestamp,
      });
    }

    // Write activity event (architectural invariant)
    await ctx.db.insert("activities", {
      agentName: args.name,
      eventType: "agent_connected",
      description: `Agent '${args.displayName ?? args.name}' (${args.role}) registered`,
      timestamp,
    });
  },
});

export const updateStatus = internalMutation({
  args: {
    agentName: v.string(),
    status: agentStatusValidator,
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      return;
    }

    const timestamp = new Date().toISOString();
    await ctx.db.patch(agent._id, {
      status: args.status,
      lastActiveAt: timestamp,
    });
  },
});

export const getByName = query({
  args: {
    name: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();
  },
});

export const listByIds = query({
  args: {
    ids: v.array(v.id("agents")),
  },
  handler: async (ctx, args) => {
    const results = await Promise.all(args.ids.map((id) => ctx.db.get(id)));
    return results.filter((doc) => doc !== null && !doc.deletedAt);
  },
});

export const updateConfig = mutation({
  args: {
    name: v.string(),
    displayName: v.optional(v.string()),
    role: v.optional(v.string()),
    prompt: v.optional(v.string()),
    soul: v.optional(v.string()),
    skills: v.optional(v.array(v.string())),
    model: v.optional(v.string()),
    reasoningLevel: v.optional(v.string()),
    interactiveProvider: v.optional(interactiveProviderValidator),
    claudeCodeOpts: v.optional(
      v.object({
        permissionMode: v.optional(v.string()),
        maxBudgetUsd: v.optional(v.number()),
        maxTurns: v.optional(v.number()),
      }),
    ),
    variables: v.optional(v.array(v.object({ name: v.string(), value: v.string() }))),
  },
  handler: async (ctx, args) => {
    // NOTE: skill validation skipped — updateConfig is called from the dashboard
    // and may set skills from squad context. Validation at squad graph publication.

    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.name}' not found`);
    }

    const timestamp = new Date().toISOString();
    const updates: Record<string, unknown> = { lastActiveAt: timestamp };

    if (args.displayName !== undefined) updates.displayName = args.displayName;
    if (args.role !== undefined) updates.role = args.role;
    if (args.prompt !== undefined) updates.prompt = args.prompt;
    if (args.soul !== undefined) updates.soul = args.soul;
    if (args.skills !== undefined) updates.skills = args.skills;
    if (args.model !== undefined) updates.model = args.model;
    if (args.reasoningLevel !== undefined) updates.reasoningLevel = args.reasoningLevel;
    if (args.interactiveProvider !== undefined)
      updates.interactiveProvider = args.interactiveProvider;
    if (args.claudeCodeOpts !== undefined) updates.claudeCodeOpts = args.claudeCodeOpts;
    if (args.variables !== undefined) updates.variables = args.variables;

    await ctx.db.patch(agent._id, updates);

    // Write activity event
    await ctx.db.insert("activities", {
      agentName: args.name,
      eventType: "agent_config_updated",
      description: `Agent '${args.displayName || agent.displayName}' configuration updated`,
      timestamp,
    });
  },
});

export const setEnabled = mutation({
  args: {
    agentName: v.string(),
    enabled: v.boolean(),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.agentName}' not found`);
    }

    // System agents cannot be disabled
    if (agent.isSystem) {
      throw new ConvexError(`Cannot change enabled state of system agent '${args.agentName}'`);
    }

    const timestamp = new Date().toISOString();
    await ctx.db.patch(agent._id, {
      enabled: args.enabled,
      lastActiveAt: timestamp,
    });

    // Write activity event
    await ctx.db.insert("activities", {
      agentName: args.agentName,
      eventType: args.enabled ? "agent_activated" : "agent_deactivated",
      description: `Agent '${agent.displayName}' ${args.enabled ? "activated" : "deactivated"}`,
      timestamp,
    });
  },
});

export const softDeleteAgent = mutation({
  args: {
    agentName: v.string(),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.agentName}' not found`);
    }

    if (agent.isSystem) {
      throw new ConvexError(`Cannot delete system agent '${args.agentName}'`);
    }

    const timestamp = new Date().toISOString();
    await ctx.db.patch(agent._id, { deletedAt: timestamp });

    await ctx.db.insert("activities", {
      agentName: args.agentName,
      eventType: "agent_deleted",
      description: `Agent '${agent.displayName}' deleted`,
      timestamp,
    });
  },
});

export const listDeleted = query({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("agents").collect();
    return all.filter((a) => !!a.deletedAt);
  },
});

export const upsertMemoryBackup = internalMutation({
  args: {
    agentName: v.string(),
    boards: v.array(
      v.object({
        boardName: v.string(),
        memoryContent: v.optional(v.string()),
        historyContent: v.optional(v.string()),
      }),
    ),
    globalMemoryContent: v.optional(v.string()),
    globalHistoryContent: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.agentName}' not found`);
    }

    await ctx.db.patch(agent._id, {
      memoryBackup: {
        boards: args.boards,
        globalMemoryContent: args.globalMemoryContent,
        globalHistoryContent: args.globalHistoryContent,
        lastBackupAt: new Date().toISOString(),
      },
    });
  },
});

export const restoreAgent = mutation({
  args: {
    agentName: v.string(),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      throw new ConvexError(`Agent '${args.agentName}' not found`);
    }

    if (!agent.deletedAt) {
      throw new ConvexError(`Agent '${args.agentName}' is not deleted`);
    }

    const timestamp = new Date().toISOString();
    // Only clear deletedAt — memoryBackup is kept as a persistent backup.
    await ctx.db.patch(agent._id, { deletedAt: undefined });

    await ctx.db.insert("activities", {
      agentName: args.agentName,
      eventType: "agent_restored",
      description: `Agent '${agent.displayName}' restored`,
      timestamp,
    });
  },
});

export const getMemoryBackup = query({
  args: {
    agentName: v.string(),
  },
  handler: async (ctx, args) => {
    const agent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.agentName))
      .first();

    if (!agent) {
      return null;
    }

    return agent.memoryBackup ?? null;
  },
});

export const publishProjection = mutation({
  args: {
    name: v.string(),
    displayName: v.optional(v.string()),
    role: v.string(),
    prompt: v.string(),
    soul: v.string(),
    skills: v.array(v.string()),
    model: v.optional(v.string()),
    interactiveProvider: v.optional(interactiveProviderValidator),
    compiledFromSpecId: v.string(),
    compiledFromVersion: v.number(),
    compiledAt: v.string(),
  },
  handler: async (ctx, args) => {
    if (args.skills.length > 0) {
      await validateSkillReferences(
        ctx as unknown as Parameters<typeof validateSkillReferences>[0],
        args.skills,
        args.name,
      );
    }

    const existing = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", args.name))
      .first();

    const timestamp = new Date().toISOString();

    if (existing) {
      // Guard: refuse to publish to a soft-deleted agent. A deleted agent must
      // be explicitly restored before it can receive new projection data.
      if (existing.deletedAt) {
        throw new ConvexError(
          `Cannot publish projection to deleted agent '${args.name}' — restore it first.`,
        );
      }
      const patch: Record<string, unknown> = {
        displayName: args.displayName ?? undefined,
        role: args.role,
        // publishProjection always overwrites prompt/soul with the compiled values.
        prompt: args.prompt,
        soul: args.soul,
        skills: args.skills,
        compiledFromSpecId: args.compiledFromSpecId,
        compiledFromVersion: args.compiledFromVersion,
        compiledAt: args.compiledAt,
        lastActiveAt: timestamp,
      };
      if (args.model !== undefined) patch.model = args.model;
      if (args.interactiveProvider !== undefined)
        patch.interactiveProvider = args.interactiveProvider;
      await ctx.db.patch(existing._id, patch);
    } else {
      await ctx.db.insert("agents", {
        name: args.name,
        displayName: args.displayName ?? undefined,
        role: args.role,
        prompt: args.prompt,
        soul: args.soul,
        skills: args.skills,
        status: "idle",
        enabled: true,
        model: args.model,
        interactiveProvider: args.interactiveProvider,
        compiledFromSpecId: args.compiledFromSpecId,
        compiledFromVersion: args.compiledFromVersion,
        compiledAt: args.compiledAt,
        lastActiveAt: timestamp,
      });
    }

    // Write activity event
    await ctx.db.insert("activities", {
      agentName: args.name,
      eventType: "agent_config_updated",
      description: `Agent '${args.displayName ?? args.name}' runtime projection published from spec '${args.compiledFromSpecId}' v${args.compiledFromVersion}`,
      timestamp,
    });
  },
});

export const deactivateExcept = internalMutation({
  args: {
    activeNames: v.array(v.string()),
  },
  handler: async (ctx, args) => {
    const allAgents = await ctx.db.query("agents").collect();
    const timestamp = new Date().toISOString();

    for (const agent of allAgents) {
      if (agent.isSystem) continue;
      if (!args.activeNames.includes(agent.name)) {
        await ctx.db.patch(agent._id, {
          status: "idle",
          lastActiveAt: timestamp,
        });
      }
    }
  },
});

export const incrementTaskMetric = internalMutation({
  args: { agentName: v.string() },
  handler: async (ctx, args) => {
    await incrementAgentTaskMetric(ctx.db as unknown as AgentMetricDb, args.agentName);
  },
});

export const incrementStepMetric = internalMutation({
  args: { agentName: v.string() },
  handler: async (ctx, args) => {
    await incrementAgentStepMetric(ctx.db as unknown as AgentMetricDb, args.agentName);
  },
});

export const renameLeadAgentToOrchestrator = internalMutation({
  args: {
    dryRun: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    const dryRun = args.dryRun === true;
    const changes: Record<string, number> = {
      activities: 0,
      agents: 0,
      boards: 0,
      messages: 0,
      reviewSpecs: 0,
      steps: 0,
      tasks: 0,
    };
    const conflicts: string[] = [];

    const patchDoc = async (
      table: keyof typeof changes,
      id: string,
      patch: Record<string, unknown>,
    ) => {
      if (!Object.keys(patch).length) return;
      changes[table] += 1;
      if (!dryRun) {
        await ctx.db.patch(id as never, patch);
      }
    };

    const existingOrchestratorAgent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", ORCHESTRATOR_AGENT_NAME))
      .first();

    const existingLeadAgent = await ctx.db
      .query("agents")
      .withIndex("by_name", (q) => q.eq("name", LEGACY_LEAD_AGENT_NAME))
      .first();

    if (
      existingLeadAgent &&
      existingOrchestratorAgent &&
      existingLeadAgent._id !== existingOrchestratorAgent._id
    ) {
      conflicts.push(
        `agents:${String(existingLeadAgent._id)} cannot rename '${LEGACY_LEAD_AGENT_NAME}' because '${ORCHESTRATOR_AGENT_NAME}' already exists`,
      );
      return { dryRun, changes, conflicts };
    }

    for (const agent of await ctx.db.query("agents").collect()) {
      const patch: Record<string, unknown> = {};
      const nextName = replaceLegacyAgentName(agent.name);
      if (nextName !== agent.name) patch.name = nextName;

      const nextDisplayName = normalizeAgentDisplayName(agent.displayName);
      if (nextDisplayName !== agent.displayName) patch.displayName = nextDisplayName;

      const nextRole = normalizeAgentRole(agent.role);
      if (nextRole !== agent.role) patch.role = nextRole;

      const nextPrompt = replaceLegacyText(agent.prompt);
      if (nextPrompt !== agent.prompt) patch.prompt = nextPrompt;

      const nextSoul = replaceLegacyText(agent.soul);
      if (nextSoul !== agent.soul) patch.soul = nextSoul;

      await patchDoc("agents", String(agent._id), patch);
    }

    for (const board of await ctx.db.query("boards").collect()) {
      const patch: Record<string, unknown> = {};
      const nextEnabledAgents = replaceLegacyStringArray(board.enabledAgents);
      if (nextEnabledAgents) patch.enabledAgents = nextEnabledAgents;

      if (Array.isArray(board.agentMemoryModes)) {
        const nextModes = board.agentMemoryModes.map((entry) => {
          const nextAgentName = replaceLegacyAgentName(entry.agentName);
          return nextAgentName === entry.agentName ? entry : { ...entry, agentName: nextAgentName };
        });
        if (nextModes.some((entry, index) => entry !== board.agentMemoryModes?.[index])) {
          patch.agentMemoryModes = nextModes;
        }
      }

      await patchDoc("boards", String(board._id), patch);
    }

    for (const task of await ctx.db.query("tasks").collect()) {
      const patch: Record<string, unknown> = {};
      const nextAssignedAgent = replaceLegacyAgentName(task.assignedAgent);
      if (nextAssignedAgent !== task.assignedAgent) patch.assignedAgent = nextAssignedAgent;

      const nextSourceAgent = replaceLegacyAgentName(task.sourceAgent);
      if (nextSourceAgent !== task.sourceAgent) patch.sourceAgent = nextSourceAgent;

      const nextRoutingMode = replaceLegacyRoutingMode(task.routingMode);
      if (nextRoutingMode !== task.routingMode) patch.routingMode = nextRoutingMode;

      const nextExecutionPlan = normalizeExecutionPlan(
        task.executionPlan as Record<string, unknown>,
      );
      if (nextExecutionPlan) patch.executionPlan = nextExecutionPlan;

      await patchDoc("tasks", String(task._id), patch);
    }

    for (const step of await ctx.db.query("steps").collect()) {
      const nextAssignedAgent = replaceLegacyAgentName(step.assignedAgent);
      if (nextAssignedAgent !== step.assignedAgent) {
        await patchDoc("steps", String(step._id), { assignedAgent: nextAssignedAgent });
      }
    }

    for (const message of await ctx.db.query("messages").collect()) {
      const legacyMessage = message as Record<string, unknown>;
      const patch: Record<string, unknown> = {};
      const nextAuthorName = replaceLegacyAgentName(message.authorName);
      if (nextAuthorName !== message.authorName) patch.authorName = nextAuthorName;

      const nextType = replaceLegacyThreadType(message.type);
      if (nextType !== message.type) patch.type = nextType;

      if (legacyMessage.leadAgentConversation !== undefined) {
        patch.orchestratorAgentConversation =
          legacyMessage.orchestratorAgentConversation ?? legacyMessage.leadAgentConversation;
        patch.leadAgentConversation = undefined;
      }

      await patchDoc("messages", String(message._id), patch);
    }

    for (const activity of await ctx.db.query("activities").collect()) {
      const patch: Record<string, unknown> = {};
      const nextAgentName = replaceLegacyAgentName(activity.agentName);
      if (nextAgentName !== activity.agentName) {
        patch.agentName = nextAgentName;
      }
      const nextDescription = replaceLegacyText(activity.description);
      if (nextDescription !== activity.description) patch.description = nextDescription;
      await patchDoc("activities", String(activity._id), patch);
    }

    for (const reviewSpec of await ctx.db.query("reviewSpecs").collect()) {
      const patch: Record<string, unknown> = {};
      const nextReviewerPolicy = replaceLegacyAgentName(reviewSpec.reviewerPolicy);
      if (nextReviewerPolicy !== reviewSpec.reviewerPolicy) {
        patch.reviewerPolicy = nextReviewerPolicy;
      }
      const nextRejectionRoutingPolicy = replaceLegacyAgentName(reviewSpec.rejectionRoutingPolicy);
      if (nextRejectionRoutingPolicy !== reviewSpec.rejectionRoutingPolicy) {
        patch.rejectionRoutingPolicy = nextRejectionRoutingPolicy;
      }
      await patchDoc("reviewSpecs", String(reviewSpec._id), patch);
    }

    return { dryRun, changes, conflicts };
  },
});

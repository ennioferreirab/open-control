import { NextResponse } from "next/server";
import { ConvexHttpClient } from "convex/browser";

type AdminConvexClient = ConvexHttpClient & {
  query(name: string, args: Record<string, unknown>): Promise<unknown>;
  setAdminAuth(token: string): void;
};

function getClient(): AdminConvexClient {
  const client = new ConvexHttpClient(process.env.NEXT_PUBLIC_CONVEX_URL!) as AdminConvexClient;
  client.setAdminAuth(process.env.CONVEX_ADMIN_KEY!);
  return client;
}

function parseSkillMetadata(raw: unknown): unknown {
  if (typeof raw !== "string") {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export async function GET() {
  try {
    const convex = getClient();

    const [agents, skills, reviewSpecs, connectedModelsRaw] = (await Promise.all([
      convex.query("agents:list", {}),
      convex.query("skills:list", {}),
      convex.query("reviewSpecs:listByStatus", { status: "published" }),
      convex.query("settings:get", { key: "connected_models" }),
    ])) as [
      Array<Record<string, unknown>>,
      Array<Record<string, unknown>>,
      Array<Record<string, unknown>>,
      string | null,
    ];

    const activeAgents = (agents as Array<Record<string, unknown>>)
      .filter(
        (agent) =>
          !agent.deletedAt &&
          agent.enabled !== false &&
          agent.isSystem !== true &&
          agent.role !== "remote-terminal",
      )
      .map((agent) => ({
        name: agent.name,
        displayName: agent.displayName,
        role: agent.role,
        prompt: agent.prompt,
        model: agent.model,
        skills: Array.isArray(agent.skills) ? agent.skills : [],
        soul: agent.soul,
      }));

    const knownSkills = (skills as Array<Record<string, unknown>>).map((skill) => ({
      name: skill.name,
      description: skill.description,
      source: skill.source,
      always: skill.always === true,
      available: skill.available === true,
      supportedProviders: Array.isArray(skill.supportedProviders)
        ? skill.supportedProviders.filter((value) => typeof value === "string")
        : [],
      requires: typeof skill.requires === "string" ? skill.requires : null,
      metadata: parseSkillMetadata(skill.metadata),
    }));

    const availableSkills = knownSkills
      .filter((skill) => skill.available === true)
      .map((skill) => ({
        name: skill.name,
        description: skill.description,
        source: skill.source,
        always: skill.always,
        supportedProviders: skill.supportedProviders,
        requires: skill.requires,
        metadata: skill.metadata,
      }));

    let availableModels: string[] = [];
    if (connectedModelsRaw) {
      try {
        const parsed = JSON.parse(connectedModelsRaw);
        availableModels = Array.isArray(parsed)
          ? parsed.filter((value) => typeof value === "string")
          : [];
      } catch {
        availableModels = [];
      }
    }

    const availableReviewSpecs = reviewSpecs.map((spec) => ({
      id: spec._id,
      name: spec.name,
      scope: spec.scope,
      approvalThreshold: spec.approvalThreshold,
      reviewerPolicy: typeof spec.reviewerPolicy === "string" ? spec.reviewerPolicy : null,
      rejectionRoutingPolicy:
        typeof spec.rejectionRoutingPolicy === "string" ? spec.rejectionRoutingPolicy : null,
    }));

    return NextResponse.json({
      activeAgents,
      availableSkills,
      knownSkills,
      availableReviewSpecs,
      availableModels,
    });
  } catch (error) {
    console.error("Failed to build squad authoring context:", error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Failed to load squad authoring context",
      },
      { status: 500 },
    );
  }
}

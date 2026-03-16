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

export async function GET() {
  try {
    const convex = getClient();

    const [agents, skills, connectedModelsRaw] = (await Promise.all([
      convex.query("agents:list", {}),
      convex.query("skills:list", {}),
      convex.query("settings:get", { key: "connected_models" }),
    ])) as [Array<Record<string, unknown>>, Array<Record<string, unknown>>, string | null];

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

    const availableSkills = (skills as Array<Record<string, unknown>>)
      .filter((skill) => skill.available === true)
      .map((skill) => ({
        name: skill.name,
        description: skill.description,
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

    return NextResponse.json({ activeAgents, availableSkills, availableModels });
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

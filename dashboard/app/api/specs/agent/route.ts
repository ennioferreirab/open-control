import { NextRequest, NextResponse } from "next/server";
import { ConvexHttpClient } from "convex/browser";

type AdminConvexClient = ConvexHttpClient & {
  mutation(name: string, args: Record<string, unknown>): Promise<unknown>;
  setAdminAuth(token: string): void;
};

function getClient(): AdminConvexClient {
  const client = new ConvexHttpClient(
    process.env.CONVEX_URL || process.env.NEXT_PUBLIC_CONVEX_URL!,
  ) as AdminConvexClient;
  client.setAdminAuth(process.env.CONVEX_ADMIN_KEY!);
  return client;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, displayName, role, ...optional } = body;

    if (!name || !role) {
      return NextResponse.json({ error: "name and role are required" }, { status: 400 });
    }

    const convex = getClient();

    const specId = await convex.mutation("agentSpecs:createDraft", {
      name,
      ...(displayName !== undefined ? { displayName } : {}),
      role,
      ...optional,
    });

    await convex.mutation("agentSpecs:publish", { specId: String(specId) });

    return NextResponse.json({ success: true, specId });
  } catch (error) {
    console.error("Agent spec creation failed:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to create agent spec" },
      { status: 500 },
    );
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, ...updates } = body;

    if (!name || typeof name !== "string") {
      return NextResponse.json({ error: "name is required" }, { status: 400 });
    }

    if (Object.keys(updates).length === 0) {
      return NextResponse.json(
        { error: "At least one field to update is required" },
        { status: 400 },
      );
    }

    const convex = getClient();

    await convex.mutation("agents:updateConfig", { name, ...updates });

    return NextResponse.json({ success: true, name });
  } catch (error) {
    console.error("Agent update failed:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to update agent" },
      { status: 500 },
    );
  }
}

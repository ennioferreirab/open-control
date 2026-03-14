import { NextRequest, NextResponse } from "next/server";
import { ConvexHttpClient } from "convex/browser";

function getClient(): ConvexHttpClient {
  const client = new ConvexHttpClient(process.env.NEXT_PUBLIC_CONVEX_URL!);
  (client as unknown as { setAdminAuth(token: string): void }).setAdminAuth(
    process.env.CONVEX_ADMIN_KEY!,
  );
  return client;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, displayName, role, ...optional } = body;

    if (!name || !displayName || !role) {
      return NextResponse.json(
        { error: "name, displayName, and role are required" },
        { status: 400 },
      );
    }

    const convex = getClient();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const specId = await (convex as any).mutation("agentSpecs:createDraft", {
      name,
      displayName,
      role,
      ...optional,
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    await (convex as any).mutation("agentSpecs:publish", { specId: String(specId) });

    return NextResponse.json({ success: true, specId });
  } catch (error) {
    console.error("Agent spec creation failed:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to create agent spec" },
      { status: 500 },
    );
  }
}

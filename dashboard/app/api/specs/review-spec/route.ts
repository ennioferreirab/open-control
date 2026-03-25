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
    const { name, scope, criteria, approvalThreshold, ...optional } = body;

    if (!name || !scope) {
      return NextResponse.json({ error: "name and scope are required" }, { status: 400 });
    }

    if (!Array.isArray(criteria) || criteria.length === 0) {
      return NextResponse.json({ error: "criteria must be a non-empty array" }, { status: 400 });
    }

    if (typeof approvalThreshold !== "number" || approvalThreshold < 0 || approvalThreshold > 1) {
      return NextResponse.json(
        { error: "approvalThreshold must be a number between 0 and 1" },
        { status: 400 },
      );
    }

    const validScopes = ["agent", "workflow", "execution"];
    if (!validScopes.includes(scope)) {
      return NextResponse.json(
        { error: `scope must be one of: ${validScopes.join(", ")}` },
        { status: 400 },
      );
    }

    const convex = getClient();

    const specId = await convex.mutation("reviewSpecs:createDraft", {
      name,
      scope,
      criteria,
      approvalThreshold,
      ...optional,
    });

    await convex.mutation("reviewSpecs:publish", { specId: String(specId) });

    return NextResponse.json({ success: true, specId });
  } catch (error) {
    console.error("Review spec creation failed:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to create review spec" },
      { status: 500 },
    );
  }
}

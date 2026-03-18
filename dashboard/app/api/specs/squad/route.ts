import { NextRequest, NextResponse } from "next/server";
import { ConvexHttpClient } from "convex/browser";
import { api } from "@/convex/_generated/api";

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
    const { squad, agents, workflows, reviewPolicy } = body;

    if (!squad || !agents || !workflows) {
      return NextResponse.json(
        { error: "squad, agents, and workflows are required" },
        { status: 400 },
      );
    }

    const convex = getClient();

    const squadId = await convex.mutation(api.squadSpecs.publishGraph, {
      graph: { squad, agents, workflows, reviewPolicy },
    });

    return NextResponse.json({ success: true, squadId });
  } catch (error) {
    console.error("Squad publish failed:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to publish squad" },
      { status: 500 },
    );
  }
}

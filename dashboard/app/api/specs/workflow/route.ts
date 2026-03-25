import { NextRequest, NextResponse } from "next/server";
import { ConvexHttpClient } from "convex/browser";
import { api } from "@/convex/_generated/api";

function getClient(): ConvexHttpClient {
  const client = new ConvexHttpClient(
    process.env.CONVEX_URL || process.env.NEXT_PUBLIC_CONVEX_URL!,
  );
  (client as unknown as { setAdminAuth(token: string): void }).setAdminAuth(
    process.env.CONVEX_ADMIN_KEY!,
  );
  return client;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { squadSpecId, workflow } = body;

    if (!squadSpecId || !workflow) {
      return NextResponse.json({ error: "squadSpecId and workflow are required" }, { status: 400 });
    }

    const convex = getClient();

    const workflowSpecId = await convex.mutation(api.workflowSpecs.publishStandalone, {
      squadSpecId,
      workflow,
    });

    return NextResponse.json({ success: true, workflowSpecId });
  } catch (error) {
    console.error("Workflow publish failed:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to publish workflow" },
      { status: 500 },
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const workflowSpecId = searchParams.get("workflowSpecId");

    if (!workflowSpecId) {
      return NextResponse.json(
        { error: "workflowSpecId query parameter is required" },
        { status: 400 },
      );
    }

    const convex = getClient();

    await convex.mutation(api.workflowSpecs.archiveWorkflow, {
      workflowSpecId: workflowSpecId as Parameters<
        typeof api.workflowSpecs.archiveWorkflow
      >[0]["workflowSpecId"],
    });

    return NextResponse.json({ success: true, workflowSpecId });
  } catch (error) {
    console.error("Workflow archive failed:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to archive workflow" },
      { status: 500 },
    );
  }
}

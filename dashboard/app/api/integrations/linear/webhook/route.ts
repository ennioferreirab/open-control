/**
 * Linear webhook receiver.
 *
 * Validates HMAC-SHA256 signatures, routes issue/comment events to the
 * appropriate Convex mutations, and always returns 200 to prevent Linear
 * from retrying on processing errors.
 */
import { NextResponse } from "next/server";
import { ConvexHttpClient } from "convex/browser";
import { verifyLinearWebhookSignature, type LinearWebhookPayload } from "@/lib/integrations/linear";

// Linear state type → MC task status mapping.
// Only maps to statuses accepted by validateInboundStatus:
// inbox, assigned, in_progress, review, done.
const LINEAR_STATE_TO_MC_STATUS: Record<string, string> = {
  triage: "inbox",
  backlog: "inbox",
  unstarted: "inbox",
  started: "in_progress",
  completed: "done",
  canceled: "done",
};

function getConvexClient(): ConvexHttpClient & {
  mutation(name: string, args: Record<string, unknown>): Promise<unknown>;
} {
  const url = process.env.NEXT_PUBLIC_CONVEX_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_CONVEX_URL is not set");
  }
  const client = new ConvexHttpClient(url) as ConvexHttpClient & {
    mutation(name: string, args: Record<string, unknown>): Promise<unknown>;
    setAdminAuth(token: string): void;
  };
  const adminKey = process.env.CONVEX_ADMIN_KEY;
  if (adminKey) {
    client.setAdminAuth(adminKey);
  }
  return client;
}

export async function POST(request: Request) {
  const rawBody = await request.text();

  // Validate HMAC signature first — reject unauthenticated requests before
  // spending resources on JSON parsing and business logic.
  const webhookSecret = process.env.MC_LINEAR_WEBHOOK_SECRET;
  if (webhookSecret) {
    const signature = request.headers.get("linear-signature") ?? "";
    if (!verifyLinearWebhookSignature(rawBody, signature, webhookSecret)) {
      return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
    }
  }

  let payload: LinearWebhookPayload;
  try {
    payload = JSON.parse(rawBody) as LinearWebhookPayload;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // Skip events from our own application to prevent feedback loops
  if (payload.actor?.type === "application") {
    return NextResponse.json({ ok: true, skipped: "application_actor" });
  }

  try {
    const convex = getConvexClient();
    const { action, type, data } = payload;
    const now = new Date().toISOString();

    if (type === "Issue") {
      if (action === "create") {
        const labels = (data.labels as Array<{ name: string }> | undefined) ?? [];

        await convex.mutation("integrations:webhookProcessIssue", {
          platform: "linear",
          externalId: (data.id as string) || "",
          externalUrl: (data.url as string) || undefined,
          title: (data.title as string) || "Untitled",
          description: (data.description as string) || undefined,
          status: "inbox",
          tags: labels.map((l) => l.name),
          timestamp: now,
        });
      } else if (
        action === "update" &&
        payload.updatedFrom &&
        ("state" in payload.updatedFrom || "stateId" in payload.updatedFrom)
      ) {
        // Only process events where the state actually changed
        const newState = data.state as { type?: string } | undefined;
        const stateType = newState?.type ?? "";
        const mcStatus = LINEAR_STATE_TO_MC_STATUS[stateType] ?? "inbox";

        await convex.mutation("integrations:webhookProcessStatusChange", {
          platform: "linear",
          externalId: (data.id as string) || "",
          newStatus: mcStatus,
          timestamp: now,
        });
      }
    } else if (type === "Comment" && action === "create") {
      const commentBody = (data.body as string) ?? "";

      // Skip MC-originated comments to prevent feedback loops
      if (commentBody.trim().startsWith("[MC]")) {
        return NextResponse.json({ ok: true, skipped: "mc_comment" });
      }

      // The issue ID is either at data.issueId or nested under data.issue.id
      const issueId =
        (data.issueId as string) || ((data.issue as { id?: string } | undefined)?.id ?? "");

      const user = data.user as { name?: string } | undefined;

      await convex.mutation("integrations:webhookProcessComment", {
        platform: "linear",
        externalId: issueId,
        authorName: user?.name ?? "linear-user",
        content: commentBody,
        timestamp: now,
      });
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[Linear webhook] Processing error:", error);
    // Always return 200 to prevent Linear from retrying on server errors
    return NextResponse.json({ ok: true, error: "Processing failed" });
  }
}

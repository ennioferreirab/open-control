/**
 * Linear webhook signature validation helper.
 */
import { createHmac, timingSafeEqual } from "crypto";

/**
 * Verify Linear webhook HMAC-SHA256 signature.
 * Uses crypto.timingSafeEqual for constant-time comparison.
 */
export function verifyLinearWebhookSignature(
  rawBody: string,
  signature: string,
  secret: string,
): boolean {
  if (!signature || !secret) return false;

  const expected = createHmac("sha256", secret).update(rawBody).digest("hex");

  if (expected.length !== signature.length) return false;

  return timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
}

/**
 * Linear webhook event types we handle.
 */
export type LinearWebhookAction = "create" | "update" | "remove";
export type LinearWebhookType = "Issue" | "Comment" | "Document";

export interface LinearWebhookPayload {
  action: LinearWebhookAction;
  type: LinearWebhookType;
  data: Record<string, unknown>;
  url?: string;
  createdAt?: string;
  webhookId?: string;
  updatedFrom?: Record<string, unknown>;
  actor?: {
    id: string;
    name: string;
    type: string;
  };
}

"use client";

import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

/** Wraps the tagAttributeValues.upsert mutation. */
export function useUpsertTagAttributeValue() {
  return useMutation(api.tagAttributeValues.upsert);
}

export type UpsertTagAttributeValueArgs = {
  taskId: Id<"tasks">;
  tagName: string;
  attributeId: Id<"tagAttributes">;
  value: string;
};

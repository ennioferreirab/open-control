"use client";

import { useMutation, useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Id, Doc } from "@/convex/_generated/dataModel";

/** Arguments for creating a task via the semantic API. */
export interface CreateTaskArgs {
  title: string;
  description?: string;
  tags?: string[];
  assignedAgent?: string;
  trustLevel?: string;
  supervisionMode?: "autonomous" | "supervised";
  reviewers?: string[];
  isManual?: boolean;
  boardId?: Id<"boards">;
  autoTitle?: boolean;
  files?: Array<{
    name: string;
    type: string;
    size: number;
    subfolder: string;
    uploadedAt: string;
  }>;
}

/** Arguments for upserting a tag attribute value. */
export interface UpsertAttrValueArgs {
  taskId: Id<"tasks">;
  tagName: string;
  attributeId: Id<"tagAttributes">;
  value: string;
}

/** Return type for the useTaskInputData hook. */
export interface TaskInputData {
  createTask: (args: CreateTaskArgs) => Promise<Id<"tasks">>;
  predefinedTags: Doc<"taskTags">[] | undefined;
  allAttributes: Doc<"tagAttributes">[] | undefined;
  upsertAttrValue: (args: UpsertAttrValueArgs) => Promise<void>;
  isAutoTitle: boolean;
}

export function useTaskInputData(): TaskInputData {
  const _createTask = useMutation(api.tasks.create);
  const predefinedTags = useQuery(api.taskTags.list);
  const allAttributes = useQuery(api.tagAttributes.list);
  const _upsertAttrValue = useMutation(api.tagAttributeValues.upsert);
  const autoTitleSetting = useQuery(api.settings.get, {
    key: "auto_title_enabled",
  });

  return {
    createTask: async (args: CreateTaskArgs): Promise<Id<"tasks">> => {
      return await _createTask(args);
    },
    predefinedTags,
    allAttributes,
    upsertAttrValue: async (args: UpsertAttrValueArgs): Promise<void> => {
      await _upsertAttrValue(args);
    },
    isAutoTitle: autoTitleSetting === "true",
  };
}

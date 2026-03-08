"use client";

import { useMutation, useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Id, Doc } from "@/convex/_generated/dataModel";

/** Arguments for creating a tag. */
export interface CreateTagArgs {
  name: string;
  color: string;
}

/** Arguments for removing a tag. */
export interface RemoveTagArgs {
  id: Id<"taskTags">;
}

/** Arguments for creating an attribute. */
export interface CreateAttributeArgs {
  name: string;
  type: "text" | "number" | "date" | "select";
  options?: string[];
}

/** Arguments for removing an attribute. */
export interface RemoveAttributeArgs {
  id: Id<"tagAttributes">;
}

/** Arguments for updating tag attribute IDs. */
export interface UpdateTagAttributeIdsArgs {
  tagId: Id<"taskTags">;
  attributeIds: Id<"tagAttributes">[];
}

/** Return type for the useTagsPanelData hook. */
export interface TagsPanelData {
  tags: Doc<"taskTags">[] | undefined;
  createTag: (args: CreateTagArgs) => Promise<void>;
  removeTag: (args: RemoveTagArgs) => Promise<void>;
  attributes: Doc<"tagAttributes">[] | undefined;
  createAttribute: (args: CreateAttributeArgs) => Promise<void>;
  removeAttribute: (args: RemoveAttributeArgs) => Promise<void>;
  updateTagAttributeIds: (args: UpdateTagAttributeIdsArgs) => Promise<void>;
}

export function useTagsPanelData(): TagsPanelData {
  const tags = useQuery(api.taskTags.list);
  const _createTag = useMutation(api.taskTags.create);
  const _removeTag = useMutation(api.taskTags.remove);
  const attributes = useQuery(api.tagAttributes.list);
  const _createAttribute = useMutation(api.tagAttributes.create);
  const _removeAttribute = useMutation(api.tagAttributes.remove);
  const _updateTagAttributeIds = useMutation(api.taskTags.updateAttributeIds);

  return {
    tags,
    createTag: async (args: CreateTagArgs): Promise<void> => {
      await _createTag(args);
    },
    removeTag: async (args: RemoveTagArgs): Promise<void> => {
      await _removeTag(args);
    },
    attributes,
    createAttribute: async (args: CreateAttributeArgs): Promise<void> => {
      await _createAttribute(args);
    },
    removeAttribute: async (args: RemoveAttributeArgs): Promise<void> => {
      await _removeAttribute(args);
    },
    updateTagAttributeIds: async (args: UpdateTagAttributeIdsArgs): Promise<void> => {
      await _updateTagAttributeIds(args);
    },
  };
}

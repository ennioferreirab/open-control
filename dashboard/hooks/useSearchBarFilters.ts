"use client";

import { useMemo } from "react";
import { useQuery } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";

/** An attribute record enriched on a tag. */
export type TagAttribute = Doc<"tagAttributes">;

/** A tag with its resolved attribute objects. */
export interface TagWithAttrs extends Doc<"taskTags"> {
  attrs: TagAttribute[];
}

/** Return type for the useSearchBarFilters hook. */
export interface SearchBarFiltersData {
  tags: Doc<"taskTags">[] | undefined;
  allAttributes: Doc<"tagAttributes">[] | undefined;
  attrById: Map<string, Doc<"tagAttributes">>;
  tagsWithAttrs: TagWithAttrs[];
}

export function useSearchBarFilters(): SearchBarFiltersData {
  const tags = useQuery(api.taskTags.list);
  const allAttributes = useQuery(api.tagAttributes.list);

  const attrById = useMemo(() => {
    if (!allAttributes) return new Map();
    return new Map(allAttributes.map((attribute) => [attribute._id, attribute]));
  }, [allAttributes]);

  const tagsWithAttrs: TagWithAttrs[] = useMemo(() => {
    if (!tags) return [];
    return tags
      .filter((tag) => tag.attributeIds && tag.attributeIds.length > 0)
      .map((tag) => ({
        ...tag,
        attrs: (tag.attributeIds ?? [])
          .map((id) => attrById.get(id))
          .filter(
            (attribute): attribute is NonNullable<typeof attribute> =>
              attribute != null,
          ),
      }))
      .filter((tag) => tag.attrs.length > 0);
  }, [tags, attrById]);

  return {
    tags,
    allAttributes,
    attrById,
    tagsWithAttrs,
  };
}

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

const mockCreateTag = vi.fn();
const mockRemoveTag = vi.fn();
const mockCreateAttribute = vi.fn();
const mockRemoveAttribute = vi.fn();
const mockUpdateTagAttributeIds = vi.fn();

vi.mock("convex/react", () => ({
  useMutation: (ref: string) => {
    if (ref === "taskTags:create") return mockCreateTag;
    if (ref === "taskTags:remove") return mockRemoveTag;
    if (ref === "tagAttributes:create") return mockCreateAttribute;
    if (ref === "tagAttributes:remove") return mockRemoveAttribute;
    if (ref === "taskTags:updateAttributeIds") return mockUpdateTagAttributeIds;
    return vi.fn();
  },
  useQuery: (ref: string) => {
    if (ref === "taskTags:list") {
      return [{ _id: "tag1", name: "Bug", color: "red" }];
    }
    if (ref === "tagAttributes:list") {
      return [{ _id: "attr1", name: "Priority", type: "text" }];
    }
    return undefined;
  },
}));

vi.mock("../../convex/_generated/api", () => ({
  api: {
    taskTags: {
      list: "taskTags:list",
      create: "taskTags:create",
      remove: "taskTags:remove",
      updateAttributeIds: "taskTags:updateAttributeIds",
    },
    tagAttributes: {
      list: "tagAttributes:list",
      create: "tagAttributes:create",
      remove: "tagAttributes:remove",
    },
  },
}));

import { useTagsPanelData } from "../useTagsPanelData";

describe("useTagsPanelData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateTag.mockResolvedValue(undefined);
    mockRemoveTag.mockResolvedValue(undefined);
    mockCreateAttribute.mockResolvedValue(undefined);
    mockRemoveAttribute.mockResolvedValue(undefined);
    mockUpdateTagAttributeIds.mockResolvedValue(undefined);
  });

  it("returns tags and attributes from queries", () => {
    const { result } = renderHook(() => useTagsPanelData());

    expect(result.current.tags).toEqual([
      { _id: "tag1", name: "Bug", color: "red" },
    ]);
    expect(result.current.attributes).toEqual([
      { _id: "attr1", name: "Priority", type: "text" },
    ]);
  });

  it("returns semantic functions for all mutations", () => {
    const { result } = renderHook(() => useTagsPanelData());

    expect(typeof result.current.createTag).toBe("function");
    expect(typeof result.current.removeTag).toBe("function");
    expect(typeof result.current.createAttribute).toBe("function");
    expect(typeof result.current.removeAttribute).toBe("function");
    expect(typeof result.current.updateTagAttributeIds).toBe("function");
  });

  it("createTag wraps the Convex mutation", async () => {
    const { result } = renderHook(() => useTagsPanelData());

    await act(async () => {
      await result.current.createTag({ name: "Feature", color: "blue" });
    });

    expect(mockCreateTag).toHaveBeenCalledWith({
      name: "Feature",
      color: "blue",
    });
  });

  it("removeTag wraps the Convex mutation", async () => {
    const { result } = renderHook(() => useTagsPanelData());

    await act(async () => {
      await result.current.removeTag({ id: "tag1" as never });
    });

    expect(mockRemoveTag).toHaveBeenCalledWith({ id: "tag1" });
  });

  it("createAttribute wraps the Convex mutation", async () => {
    const { result } = renderHook(() => useTagsPanelData());

    await act(async () => {
      await result.current.createAttribute({
        name: "Severity",
        type: "select",
        options: ["low", "medium", "high"],
      });
    });

    expect(mockCreateAttribute).toHaveBeenCalledWith({
      name: "Severity",
      type: "select",
      options: ["low", "medium", "high"],
    });
  });

  it("removeAttribute wraps the Convex mutation", async () => {
    const { result } = renderHook(() => useTagsPanelData());

    await act(async () => {
      await result.current.removeAttribute({ id: "attr1" as never });
    });

    expect(mockRemoveAttribute).toHaveBeenCalledWith({ id: "attr1" });
  });

  it("updateTagAttributeIds wraps the Convex mutation", async () => {
    const { result } = renderHook(() => useTagsPanelData());

    await act(async () => {
      await result.current.updateTagAttributeIds({
        tagId: "tag1" as never,
        attributeIds: ["attr1" as never],
      });
    });

    expect(mockUpdateTagAttributeIds).toHaveBeenCalledWith({
      tagId: "tag1",
      attributeIds: ["attr1"],
    });
  });
});

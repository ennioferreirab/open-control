import { describe, expect, it, vi } from "vitest";

import { searchByValue } from "./tagAttributeValues";

function getHandler() {
  return (searchByValue as unknown as {
    _handler: (
      ctx: unknown,
      args: { value: string; tagName?: string }
    ) => Promise<string[]>;
  })._handler;
}

describe("tagAttributeValues.searchByValue", () => {
  it("returns deduplicated task IDs matching value with case-insensitive tag filter", async () => {
    const allEntries = [
      { taskId: "t1", tagName: "Feature", value: "high" },
      { taskId: "t1", tagName: "Feature", value: "high priority" },
      { taskId: "t2", tagName: "Feature", value: "HIGH" },
      { taskId: "t3", tagName: "Bug", value: "high severity" },
    ];
    const collect = vi.fn(async () => allEntries);
    const query = vi.fn(() => ({ collect }));
    const handler = getHandler();

    // tagName "feature" (lowercased) should match stored "Feature" (original casing)
    const result = await handler(
      { db: { query } },
      { value: "high", tagName: "feature" }
    );

    // t3 has tagName "Bug" (not "feature"), so it's excluded
    expect(result).toEqual(["t1", "t2"]);
  });

  it("returns all matching task IDs when no tagName filter is provided", async () => {
    const allEntries = [
      { taskId: "t1", tagName: "Feature", value: "high" },
      { taskId: "t3", tagName: "Bug", value: "high severity" },
    ];
    const collect = vi.fn(async () => allEntries);
    const query = vi.fn(() => ({ collect }));
    const handler = getHandler();

    const result = await handler({ db: { query } }, { value: "high" });

    expect(result).toEqual(["t1", "t3"]);
  });

  it("returns empty array for blank value", async () => {
    const collect = vi.fn();
    const query = vi.fn(() => ({ collect }));
    const handler = getHandler();

    const result = await handler({ db: { query } }, { value: "   " });
    expect(result).toEqual([]);
    expect(query).not.toHaveBeenCalled();
  });
});

import { describe, expect, it, vi } from "vitest";

import { search } from "./tasks";

type TaskDoc = {
  _id: string;
  status: string;
  title: string;
  description?: string;
};

function getHandler() {
  return (search as unknown as {
    _handler: (
      ctx: unknown,
      args: { query: string; boardId?: string }
    ) => Promise<TaskDoc[]>;
  })._handler;
}

describe("tasks.search", () => {
  it("queries both title and description indexes and deduplicates merged results", async () => {
    const titleResults: TaskDoc[] = [
      { _id: "t1", status: "inbox", title: "OAuth setup" },
      { _id: "t2", status: "inbox", title: "Token refresh" },
    ];
    const descriptionResults: TaskDoc[] = [
      { _id: "t2", status: "inbox", title: "Token refresh" },
      { _id: "t3", status: "deleted", title: "Old task" },
      { _id: "t4", status: "review", title: "Auth docs" },
    ];

    const withSearchIndex = vi.fn(
      (indexName: string, buildQuery: (q: any) => any) => {
        const searchFn = vi.fn((_field: string, _value: string) => ({
          eq: vi.fn((_key: string, _boardId: string) => ({})),
        }));
        buildQuery({ search: searchFn });
        return {
          take: vi.fn(async () =>
            indexName === "search_title" ? titleResults : descriptionResults
          ),
        };
      }
    );

    const query = vi.fn(() => ({ withSearchIndex }));
    const handler = getHandler();

    const result = await handler(
      { db: { query } },
      { query: "OAuth", boardId: "board-1" }
    );

    expect(withSearchIndex).toHaveBeenNthCalledWith(
      1,
      "search_title",
      expect.any(Function)
    );
    expect(withSearchIndex).toHaveBeenNthCalledWith(
      2,
      "search_description",
      expect.any(Function)
    );
    expect(result.map((task) => task._id)).toEqual(["t1", "t2", "t4"]);
  });

  it("handles tasks with undefined description gracefully", async () => {
    const titleResults: TaskDoc[] = [
      { _id: "t1", status: "inbox", title: "Task without description" },
    ];
    const descriptionResults: TaskDoc[] = [];

    const withSearchIndex = vi.fn(
      (indexName: string, buildQuery: (q: any) => any) => {
        const searchFn = vi.fn((_field: string, _value: string) => ({
          eq: vi.fn((_key: string, _boardId: string) => ({})),
        }));
        buildQuery({ search: searchFn });
        return {
          take: vi.fn(async () =>
            indexName === "search_title" ? titleResults : descriptionResults
          ),
        };
      }
    );

    const query = vi.fn(() => ({ withSearchIndex }));
    const handler = getHandler();

    const result = await handler(
      { db: { query } },
      { query: "Task" }
    );

    expect(result).toHaveLength(1);
    expect(result[0]._id).toBe("t1");
  });

  it("returns an empty list for empty search input", async () => {
    const query = vi.fn();
    const handler = getHandler();

    const result = await handler({ db: { query } }, { query: "   " });
    expect(result).toEqual([]);
    expect(query).not.toHaveBeenCalled();
  });
});

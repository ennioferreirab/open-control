import { describe, it, expect, afterEach } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";
import {
  useBoardColumns,
  stepStatusToColumnStatus,
  ColumnData,
} from "./useBoardColumns";
import { Doc, Id } from "../convex/_generated/dataModel";

type Task = Doc<"tasks">;
type Step = Doc<"steps">;

function makeTask(overrides: Record<string, unknown> = {}): Task {
  return {
    _id: `task_${Math.random().toString(36).slice(2)}` as Id<"tasks">,
    _creationTime: 1000,
    title: "Test task",
    status: "inbox",
    trustLevel: "autonomous",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  } as Task;
}

function makeStep(overrides: Record<string, unknown> = {}): Step {
  return {
    _id: `step_${Math.random().toString(36).slice(2)}` as Id<"steps">,
    _creationTime: 1000,
    taskId: "task_1" as Id<"tasks">,
    title: "Test step",
    description: "Test step description",
    assignedAgent: "nanobot",
    status: "assigned",
    blockedBy: [],
    parallelGroup: 1,
    order: 1,
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  } as Step;
}

describe("stepStatusToColumnStatus", () => {
  it("maps assigned steps to assigned column by default", () => {
    expect(stepStatusToColumnStatus("assigned")).toBe("assigned");
  });

  it("maps assigned steps to in_progress when parent task is in_progress", () => {
    expect(stepStatusToColumnStatus("assigned", "in_progress")).toBe(
      "in_progress"
    );
  });

  it("maps blocked steps to assigned column by default", () => {
    expect(stepStatusToColumnStatus("blocked")).toBe("assigned");
  });

  it("maps blocked steps to in_progress when parent task is in_progress", () => {
    expect(stepStatusToColumnStatus("blocked", "in_progress")).toBe(
      "in_progress"
    );
  });

  it("maps running steps to in_progress", () => {
    expect(stepStatusToColumnStatus("running")).toBe("in_progress");
  });

  it("maps crashed steps to in_progress", () => {
    expect(stepStatusToColumnStatus("crashed")).toBe("in_progress");
  });

  it("maps completed steps to null", () => {
    expect(stepStatusToColumnStatus("completed")).toBeNull();
  });

  it("maps planned steps to null", () => {
    expect(stepStatusToColumnStatus("planned")).toBeNull();
  });
});

describe("useBoardColumns", () => {
  afterEach(() => {
    cleanup();
  });

  it("returns undefined when tasks is undefined", () => {
    const { result } = renderHook(() => useBoardColumns(undefined, []));
    expect(result.current).toBeUndefined();
  });

  it("returns undefined when steps is undefined", () => {
    const { result } = renderHook(() => useBoardColumns([], undefined));
    expect(result.current).toBeUndefined();
  });

  it("returns 5 columns with correct titles", () => {
    const { result } = renderHook(() => useBoardColumns([], []));
    expect(result.current).toHaveLength(5);
    expect(result.current!.map((c) => c.title)).toEqual([
      "Inbox",
      "Assigned",
      "In Progress",
      "Review",
      "Done",
    ]);
  });

  it("groups tasks by status into correct columns", () => {
    const tasks = [
      makeTask({ _id: "t1", status: "inbox" }),
      makeTask({ _id: "t2", status: "assigned" }),
      makeTask({ _id: "t3", status: "in_progress" }),
      makeTask({ _id: "t4", status: "review" }),
      makeTask({ _id: "t5", status: "done" }),
    ];
    const { result } = renderHook(() => useBoardColumns(tasks, []));
    const columns = result.current!;

    expect(columns[0].tasks).toHaveLength(1); // Inbox
    expect(columns[0].tasks[0]._id).toBe("t1");
    expect(columns[1].tasks).toHaveLength(1); // Assigned
    expect(columns[1].tasks[0]._id).toBe("t2");
    expect(columns[2].tasks).toHaveLength(1); // In Progress
    expect(columns[2].tasks[0]._id).toBe("t3");
    expect(columns[3].tasks).toHaveLength(1); // Review
    expect(columns[3].tasks[0]._id).toBe("t4");
    expect(columns[4].tasks).toHaveLength(1); // Done
    expect(columns[4].tasks[0]._id).toBe("t5");
  });

  it("places retrying, crashed, and failed tasks in In Progress", () => {
    const tasks = [
      makeTask({ _id: "t1", status: "retrying" }),
      makeTask({ _id: "t2", status: "crashed" }),
      makeTask({ _id: "t3", status: "failed" }),
    ];
    const { result } = renderHook(() => useBoardColumns(tasks, []));
    const inProgressCol = result.current![2];
    expect(inProgressCol.tasks).toHaveLength(3);
  });

  it("places planning and ready tasks in Assigned column", () => {
    const tasks = [
      makeTask({ _id: "t1", status: "planning" }),
      makeTask({ _id: "t2", status: "ready" }),
    ];
    const { result } = renderHook(() => useBoardColumns(tasks, []));
    const assignedCol = result.current![1];
    expect(assignedCol.tasks).toHaveLength(2);
  });

  it("sorts tasks by creation time descending", () => {
    const tasks = [
      makeTask({ _id: "t1", status: "inbox", _creationTime: 100 }),
      makeTask({ _id: "t2", status: "inbox", _creationTime: 300 }),
      makeTask({ _id: "t3", status: "inbox", _creationTime: 200 }),
    ];
    const { result } = renderHook(() => useBoardColumns(tasks, []));
    const inboxCol = result.current![0];
    expect(inboxCol.tasks.map((t) => t._id)).toEqual(["t2", "t3", "t1"]);
  });

  it("creates step groups for tasks with renderable steps", () => {
    const tasks = [
      makeTask({ _id: "task_1", status: "assigned" }),
    ];
    const steps = [
      makeStep({ taskId: "task_1", status: "assigned", order: 1 }),
      makeStep({ taskId: "task_1", status: "running", order: 2 }),
    ];
    const { result } = renderHook(() => useBoardColumns(tasks, steps));
    const columns = result.current!;

    // Task with steps should not appear as a regular task card
    const assignedCol = columns[1]; // Assigned
    expect(assignedCol.tasks).toHaveLength(0);
    expect(assignedCol.stepGroups).toHaveLength(1);
    expect(assignedCol.stepGroups[0].steps).toHaveLength(1); // only assigned step

    const inProgressCol = columns[2]; // In Progress
    expect(inProgressCol.stepGroups).toHaveLength(1);
    expect(inProgressCol.stepGroups[0].steps).toHaveLength(1); // only running step
  });

  it("skips steps for done tasks", () => {
    const tasks = [makeTask({ _id: "task_1", status: "done" })];
    const steps = [
      makeStep({ taskId: "task_1", status: "running", order: 1 }),
    ];
    const { result } = renderHook(() => useBoardColumns(tasks, steps));
    const columns = result.current!;

    // Done task should still appear as regular card in Done column
    expect(columns[4].tasks).toHaveLength(1);
    // No step groups anywhere
    for (const col of columns) {
      expect(col.stepGroups).toHaveLength(0);
    }
  });

  it("keeps review tasks as regular cards even with running steps", () => {
    const tasks = [makeTask({ _id: "task_1", status: "review" })];
    const steps = [
      makeStep({ taskId: "task_1", status: "running", order: 1 }),
    ];
    const { result } = renderHook(() => useBoardColumns(tasks, steps));
    const columns = result.current!;

    // Review task should appear as a regular card in Review column
    const reviewCol = columns[3];
    expect(reviewCol.tasks).toHaveLength(1);
    // No step groups since review tasks are excluded from step processing
    for (const col of columns) {
      expect(col.stepGroups).toHaveLength(0);
    }
  });

  it("computes totalCount as tasks + step group step counts", () => {
    const tasks = [
      makeTask({ _id: "task_1", status: "assigned" }),
      makeTask({ _id: "task_2", status: "assigned" }),
    ];
    const steps = [
      makeStep({ taskId: "task_1", status: "assigned", order: 1 }),
      makeStep({ taskId: "task_1", status: "assigned", order: 2 }),
    ];
    const { result } = renderHook(() => useBoardColumns(tasks, steps));
    const assignedCol = result.current![1];

    // task_2 is a regular card (1), task_1 has 2 steps
    expect(assignedCol.totalCount).toBe(3); // 1 regular task + 2 steps
  });

  it("filters out steps for tasks not in the visible set", () => {
    const tasks = [makeTask({ _id: "task_1", status: "inbox" })];
    const steps = [
      makeStep({ taskId: "task_other" as Id<"tasks">, status: "running" }),
    ];
    const { result } = renderHook(() => useBoardColumns(tasks, steps));
    for (const col of result.current!) {
      expect(col.stepGroups).toHaveLength(0);
    }
  });
});

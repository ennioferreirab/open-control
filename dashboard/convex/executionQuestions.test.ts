import { describe, expect, it, vi } from "vitest";

import { answerForTask, create } from "./executionQuestions";

function getCreateHandler() {
  return (
    create as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<void>;
    }
  )._handler;
}

function getAnswerHandler() {
  return (
    answerForTask as unknown as {
      _handler: (ctx: unknown, args: Record<string, unknown>) => Promise<unknown>;
    }
  )._handler;
}

describe("executionQuestions.create", () => {
  it("creates a pending question and projects waiting_user_input state", async () => {
    const inserts: Array<{ table: string; value: Record<string, unknown> }> = [];
    const patches: Array<{ id: string; patch: Record<string, unknown> }> = [];
    const ctx = {
      db: {
        insert: vi.fn(async (table: string, value: Record<string, unknown>) => {
          inserts.push({ table, value });
          return `${table}-id`;
        }),
        patch: vi.fn(async (id: string, patch: Record<string, unknown>) => {
          patches.push({ id, patch });
        }),
        query: vi.fn((table: string) => {
          if (table === "executionSessions") {
            return {
              withIndex: vi.fn(() => ({
                first: vi.fn(async () => null),
              })),
            };
          }
          if (table === "executionInteractions") {
            return {
              withIndex: vi.fn(() => ({
                order: vi.fn(() => ({
                  take: vi.fn(async () => []),
                })),
              })),
            };
          }
          throw new Error(`Unexpected table ${table}`);
        }),
      },
    };

    await getCreateHandler()(ctx, {
      questionId: "question-1",
      sessionId: "session-1",
      taskId: "task-1",
      stepId: "step-1",
      agentName: "offer-strategist",
      provider: "claude-code",
      question: "What should Easy automate first?",
      options: ["Sales", "Support"],
      createdAt: "2026-03-16T18:00:00.000Z",
    });

    expect(inserts.find((entry) => entry.table === "executionQuestions")?.value.status).toBe(
      "pending",
    );
    expect(inserts.find((entry) => entry.table === "executionSessions")?.value.state).toBe(
      "waiting_user_input",
    );
    expect(inserts.find((entry) => entry.table === "executionInteractions")?.value.kind).toBe(
      "question_requested",
    );
    expect(patches).toHaveLength(0);
  });
});

describe("executionQuestions.answerForTask", () => {
  it("answers the pending question and projects ready_to_resume state", async () => {
    const inserts: Array<{ table: string; value: Record<string, unknown> }> = [];
    const patches: Array<{ id: string; patch: Record<string, unknown> }> = [];
    const pendingQuestion = {
      _id: "question-doc-1",
      questionId: "question-1",
      sessionId: "session-1",
      taskId: "task-1",
      stepId: "step-1",
      agentName: "offer-strategist",
      provider: "claude-code",
      status: "pending",
      createdAt: "2026-03-16T18:00:00.000Z",
    };
    const existingSession = {
      _id: "session-doc-1",
      sessionId: "session-1",
      taskId: "task-1",
      stepId: "step-1",
      agentName: "offer-strategist",
      provider: "claude-code",
      state: "waiting_user_input",
      createdAt: "2026-03-16T18:00:00.000Z",
      updatedAt: "2026-03-16T18:00:00.000Z",
    };
    const ctx = {
      db: {
        insert: vi.fn(async (table: string, value: Record<string, unknown>) => {
          inserts.push({ table, value });
          return `${table}-id`;
        }),
        patch: vi.fn(async (id: string, patch: Record<string, unknown>) => {
          patches.push({ id, patch });
        }),
        query: vi.fn((table: string) => {
          if (table === "executionQuestions") {
            return {
              withIndex: vi.fn(() => ({
                first: vi.fn(async () => pendingQuestion),
              })),
            };
          }
          if (table === "executionSessions") {
            return {
              withIndex: vi.fn(() => ({
                first: vi.fn(async () => existingSession),
              })),
            };
          }
          if (table === "executionInteractions") {
            return {
              withIndex: vi.fn(() => ({
                order: vi.fn(() => ({
                  take: vi.fn(async () => []),
                })),
              })),
            };
          }
          throw new Error(`Unexpected table ${table}`);
        }),
      },
    };

    const result = await getAnswerHandler()(ctx, {
      taskId: "task-1",
      answer: "Sales",
      answeredAt: "2026-03-16T18:05:00.000Z",
    });

    expect(result).toMatchObject({
      questionId: "question-1",
      answer: "Sales",
      status: "answered",
    });
    expect(patches[0]).toEqual({
      id: "question-doc-1",
      patch: {
        status: "answered",
        answer: "Sales",
        answeredAt: "2026-03-16T18:05:00.000Z",
      },
    });
    expect(patches[1]?.patch.state).toBe("ready_to_resume");
    expect(inserts.find((entry) => entry.table === "executionInteractions")?.value.kind).toBe(
      "question_answered",
    );
  });
});

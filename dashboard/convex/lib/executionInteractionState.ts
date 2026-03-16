import type { Id } from "../_generated/dataModel";
import type { MutationCtx, QueryCtx } from "../_generated/server";
import { ConvexError } from "convex/values";

export type ExecutionInteractionState =
  | "running"
  | "waiting_user_input"
  | "ready_to_resume"
  | "paused"
  | "completed"
  | "crashed";

type SessionRecord = {
  sessionId: string;
  taskId: Id<"tasks">;
  stepId?: Id<"steps">;
  agentName: string;
  provider: string;
  state: ExecutionInteractionState;
  lastProgressMessage?: string;
  lastProgressPercentage?: number;
  finalResult?: string;
  finalResultSource?: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  crashedAt?: string;
};

type QuestionRecord = {
  questionId: string;
  sessionId: string;
  taskId: Id<"tasks">;
  stepId?: Id<"steps">;
  agentName: string;
  provider: string;
  question?: string;
  options?: string[];
  questions?: unknown;
  status: "pending" | "answered" | "cancelled" | "expired";
  answer?: string;
  createdAt: string;
  answeredAt?: string;
};

async function nextInteractionSeq(ctx: QueryCtx | MutationCtx, sessionId: string): Promise<number> {
  const last = await ctx.db
    .query("executionInteractions")
    .withIndex("by_sessionId_seq", (q) => q.eq("sessionId", sessionId))
    .order("desc")
    .take(1);
  return (last[0]?.seq ?? 0) + 1;
}

export async function appendExecutionInteraction(
  ctx: MutationCtx,
  args: {
    sessionId: string;
    taskId: Id<"tasks">;
    stepId?: Id<"steps">;
    kind: string;
    payload?: unknown;
    createdAt: string;
    agentName?: string;
    provider?: string;
  },
): Promise<void> {
  const seq = await nextInteractionSeq(ctx, args.sessionId);
  await ctx.db.insert("executionInteractions", {
    sessionId: args.sessionId,
    taskId: args.taskId,
    stepId: args.stepId,
    seq,
    kind: args.kind,
    payload: args.payload,
    createdAt: args.createdAt,
    agentName: args.agentName,
    provider: args.provider,
  });
}

export async function upsertExecutionSession(
  ctx: MutationCtx,
  args: {
    sessionId: string;
    taskId: Id<"tasks">;
    stepId?: Id<"steps">;
    agentName: string;
    provider: string;
    state: ExecutionInteractionState;
    updatedAt: string;
    createdAt?: string;
    lastProgressMessage?: string;
    lastProgressPercentage?: number;
    finalResult?: string;
    finalResultSource?: string;
    completedAt?: string;
    crashedAt?: string;
  },
): Promise<void> {
  const existing = await ctx.db
    .query("executionSessions")
    .withIndex("by_sessionId", (q) => q.eq("sessionId", args.sessionId))
    .first();

  if (existing) {
    await ctx.db.patch(existing._id, {
      taskId: args.taskId,
      stepId: args.stepId,
      agentName: args.agentName,
      provider: args.provider,
      state: args.state,
      updatedAt: args.updatedAt,
      lastProgressMessage: args.lastProgressMessage,
      lastProgressPercentage: args.lastProgressPercentage,
      finalResult: args.finalResult,
      finalResultSource: args.finalResultSource,
      completedAt: args.completedAt,
      crashedAt: args.crashedAt,
    });
    return;
  }

  await ctx.db.insert("executionSessions", {
    sessionId: args.sessionId,
    taskId: args.taskId,
    stepId: args.stepId,
    agentName: args.agentName,
    provider: args.provider,
    state: args.state,
    createdAt: args.createdAt ?? args.updatedAt,
    updatedAt: args.updatedAt,
    lastProgressMessage: args.lastProgressMessage,
    lastProgressPercentage: args.lastProgressPercentage,
    finalResult: args.finalResult,
    finalResultSource: args.finalResultSource,
    completedAt: args.completedAt,
    crashedAt: args.crashedAt,
  });
}

export async function createExecutionQuestion(
  ctx: MutationCtx,
  args: {
    questionId: string;
    sessionId: string;
    taskId: Id<"tasks">;
    stepId?: Id<"steps">;
    agentName: string;
    provider: string;
    question?: string;
    options?: string[];
    questions?: unknown;
    createdAt: string;
  },
): Promise<void> {
  await ctx.db.insert("executionQuestions", {
    questionId: args.questionId,
    sessionId: args.sessionId,
    taskId: args.taskId,
    stepId: args.stepId,
    agentName: args.agentName,
    provider: args.provider,
    question: args.question,
    options: args.options,
    questions: args.questions,
    status: "pending",
    createdAt: args.createdAt,
  });
}

export async function answerPendingExecutionQuestionForTask(
  ctx: MutationCtx,
  args: {
    taskId: Id<"tasks">;
    answer: string;
    answeredAt: string;
  },
): Promise<QuestionRecord | null> {
  const pending = await ctx.db
    .query("executionQuestions")
    .withIndex("by_taskId_status", (q) => q.eq("taskId", args.taskId).eq("status", "pending"))
    .first();
  if (!pending) {
    return null;
  }

  await ctx.db.patch(pending._id, {
    status: "answered",
    answer: args.answer,
    answeredAt: args.answeredAt,
  });
  return {
    questionId: pending.questionId,
    sessionId: pending.sessionId,
    taskId: pending.taskId,
    stepId: pending.stepId,
    agentName: pending.agentName,
    provider: pending.provider,
    question: pending.question,
    options: pending.options,
    questions: pending.questions,
    status: "answered",
    answer: args.answer,
    createdAt: pending.createdAt,
    answeredAt: args.answeredAt,
  };
}

export async function getExecutionQuestionById(
  ctx: QueryCtx,
  questionId: string,
): Promise<QuestionRecord | null> {
  const question = await ctx.db
    .query("executionQuestions")
    .withIndex("by_questionId", (q) => q.eq("questionId", questionId))
    .first();
  if (!question) {
    return null;
  }
  return question;
}

export async function requireExecutionSessionById(
  ctx: QueryCtx | MutationCtx,
  sessionId: string,
): Promise<SessionRecord> {
  const session = await ctx.db
    .query("executionSessions")
    .withIndex("by_sessionId", (q) => q.eq("sessionId", sessionId))
    .first();
  if (!session) {
    throw new ConvexError("Execution session not found");
  }
  return session;
}

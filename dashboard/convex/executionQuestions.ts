import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";

import {
  answerPendingExecutionQuestionForTask,
  appendExecutionInteraction,
  createExecutionQuestion,
  getExecutionQuestionById,
  upsertExecutionSession,
} from "./lib/executionInteractionState";

export const create = internalMutation({
  args: {
    questionId: v.string(),
    sessionId: v.string(),
    taskId: v.id("tasks"),
    stepId: v.optional(v.id("steps")),
    agentName: v.string(),
    provider: v.string(),
    question: v.optional(v.string()),
    options: v.optional(v.array(v.string())),
    questions: v.optional(v.any()),
    createdAt: v.string(),
  },
  handler: async (ctx, args) => {
    await createExecutionQuestion(ctx, args);
    await upsertExecutionSession(ctx, {
      sessionId: args.sessionId,
      taskId: args.taskId,
      stepId: args.stepId,
      agentName: args.agentName,
      provider: args.provider,
      state: "waiting_user_input",
      updatedAt: args.createdAt,
      createdAt: args.createdAt,
    });
    await appendExecutionInteraction(ctx, {
      sessionId: args.sessionId,
      taskId: args.taskId,
      stepId: args.stepId,
      kind: "question_requested",
      payload: {
        questionId: args.questionId,
        question: args.question,
        options: args.options,
        questions: args.questions,
      },
      createdAt: args.createdAt,
      agentName: args.agentName,
      provider: args.provider,
    });
  },
});

export const answerForTask = internalMutation({
  args: {
    taskId: v.id("tasks"),
    answer: v.string(),
    answeredAt: v.string(),
  },
  handler: async (ctx, args) => {
    const question = await answerPendingExecutionQuestionForTask(ctx, args);
    if (!question) {
      return null;
    }
    await upsertExecutionSession(ctx, {
      sessionId: question.sessionId,
      taskId: question.taskId,
      stepId: question.stepId,
      agentName: question.agentName,
      provider: question.provider,
      state: "ready_to_resume",
      updatedAt: args.answeredAt,
    });
    await appendExecutionInteraction(ctx, {
      sessionId: question.sessionId,
      taskId: question.taskId,
      stepId: question.stepId,
      kind: "question_answered",
      payload: {
        questionId: question.questionId,
        answer: args.answer,
      },
      createdAt: args.answeredAt,
      agentName: question.agentName,
      provider: question.provider,
    });
    return question;
  },
});

export const getByQuestionId = query({
  args: { questionId: v.string() },
  handler: async (ctx, args) => {
    return await getExecutionQuestionById(ctx, args.questionId);
  },
});

export const hasPendingForTask = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    const pending = await ctx.db
      .query("executionQuestions")
      .withIndex("by_taskId_status", (q) => q.eq("taskId", args.taskId).eq("status", "pending"))
      .first();
    return pending !== null;
  },
});

export const getPendingForTask = query({
  args: { taskId: v.id("tasks") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("executionQuestions")
      .withIndex("by_taskId_status", (q) => q.eq("taskId", args.taskId).eq("status", "pending"))
      .first();
  },
});

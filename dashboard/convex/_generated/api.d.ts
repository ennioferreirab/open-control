/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as activities from "../activities.js";
import type * as agentSpecs from "../agentSpecs.js";
import type * as agents from "../agents.js";
import type * as boardSquadBindings from "../boardSquadBindings.js";
import type * as boards from "../boards.js";
import type * as chats from "../chats.js";
import type * as interactiveSessions from "../interactiveSessions.js";
import type * as reviewSpecs from "../reviewSpecs.js";
import type * as squadSpecs from "../squadSpecs.js";
import type * as workflowSpecs from "../workflowSpecs.js";
import type * as lib_readModels from "../lib/readModels.js";
import type * as lib_stepLifecycle from "../lib/stepLifecycle.js";
import type * as lib_taskArchive from "../lib/taskArchive.js";
import type * as lib_taskDetailView from "../lib/taskDetailView.js";
import type * as lib_taskFiles from "../lib/taskFiles.js";
import type * as lib_taskLifecycle from "../lib/taskLifecycle.js";
import type * as lib_taskMerge from "../lib/taskMerge.js";
import type * as lib_taskMetadata from "../lib/taskMetadata.js";
import type * as lib_taskPlanning from "../lib/taskPlanning.js";
import type * as lib_taskReview from "../lib/taskReview.js";
import type * as lib_taskStatus from "../lib/taskStatus.js";
import type * as lib_threadRules from "../lib/threadRules.js";
import type * as lib_workflowContract from "../lib/workflowContract.js";
import type * as lib_workflowHelpers from "../lib/workflowHelpers.js";
import type * as messages from "../messages.js";
import type * as settings from "../settings.js";
import type * as skills from "../skills.js";
import type * as steps from "../steps.js";
import type * as tagAttributeValues from "../tagAttributeValues.js";
import type * as tagAttributes from "../tagAttributes.js";
import type * as taskTags from "../taskTags.js";
import type * as tasks from "../tasks.js";
import type * as terminalSessions from "../terminalSessions.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  activities: typeof activities;
  agentSpecs: typeof agentSpecs;
  agents: typeof agents;
  boardSquadBindings: typeof boardSquadBindings;
  boards: typeof boards;
  chats: typeof chats;
  interactiveSessions: typeof interactiveSessions;
  reviewSpecs: typeof reviewSpecs;
  squadSpecs: typeof squadSpecs;
  workflowSpecs: typeof workflowSpecs;
  "lib/readModels": typeof lib_readModels;
  "lib/stepLifecycle": typeof lib_stepLifecycle;
  "lib/taskArchive": typeof lib_taskArchive;
  "lib/taskDetailView": typeof lib_taskDetailView;
  "lib/taskFiles": typeof lib_taskFiles;
  "lib/taskLifecycle": typeof lib_taskLifecycle;
  "lib/taskMerge": typeof lib_taskMerge;
  "lib/taskMetadata": typeof lib_taskMetadata;
  "lib/taskPlanning": typeof lib_taskPlanning;
  "lib/taskReview": typeof lib_taskReview;
  "lib/taskStatus": typeof lib_taskStatus;
  "lib/threadRules": typeof lib_threadRules;
  "lib/workflowContract": typeof lib_workflowContract;
  "lib/workflowHelpers": typeof lib_workflowHelpers;
  messages: typeof messages;
  settings: typeof settings;
  skills: typeof skills;
  steps: typeof steps;
  tagAttributeValues: typeof tagAttributeValues;
  tagAttributes: typeof tagAttributes;
  taskTags: typeof taskTags;
  tasks: typeof tasks;
  terminalSessions: typeof terminalSessions;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};

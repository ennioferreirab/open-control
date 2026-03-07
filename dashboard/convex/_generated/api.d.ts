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
import type * as agents from "../agents.js";
import type * as boards from "../boards.js";
import type * as chats from "../chats.js";
import type * as lib_readModels from "../lib/readModels.js";
import type * as lib_stepLifecycle from "../lib/stepLifecycle.js";
import type * as lib_taskLifecycle from "../lib/taskLifecycle.js";
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
  agents: typeof agents;
  boards: typeof boards;
  chats: typeof chats;
  "lib/readModels": typeof lib_readModels;
  "lib/stepLifecycle": typeof lib_stepLifecycle;
  "lib/taskLifecycle": typeof lib_taskLifecycle;
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

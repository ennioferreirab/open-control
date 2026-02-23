// Task status values
export const TASK_STATUS = {
  INBOX: "inbox",
  ASSIGNED: "assigned",
  IN_PROGRESS: "in_progress",
  REVIEW: "review",
  DONE: "done",
  RETRYING: "retrying",
  CRASHED: "crashed",
  DELETED: "deleted",
} as const;

// Trust level values
export const TRUST_LEVEL = {
  AUTONOMOUS: "autonomous",
  AGENT_REVIEWED: "agent_reviewed",
  HUMAN_APPROVED: "human_approved",
} as const;

// Agent status values
export const AGENT_STATUS = {
  ACTIVE: "active",
  IDLE: "idle",
  CRASHED: "crashed",
} as const;

// Activity event type values
export const ACTIVITY_EVENT_TYPE = {
  TASK_CREATED: "task_created",
  TASK_ASSIGNED: "task_assigned",
  TASK_STARTED: "task_started",
  TASK_COMPLETED: "task_completed",
  TASK_CRASHED: "task_crashed",
  TASK_RETRYING: "task_retrying",
  REVIEW_REQUESTED: "review_requested",
  REVIEW_FEEDBACK: "review_feedback",
  REVIEW_APPROVED: "review_approved",
  HITL_REQUESTED: "hitl_requested",
  HITL_APPROVED: "hitl_approved",
  HITL_DENIED: "hitl_denied",
  AGENT_CONNECTED: "agent_connected",
  AGENT_DISCONNECTED: "agent_disconnected",
  AGENT_CRASHED: "agent_crashed",
  SYSTEM_ERROR: "system_error",
  TASK_DELETED: "task_deleted",
  TASK_RESTORED: "task_restored",
} as const;

// Message type values
export const MESSAGE_TYPE = {
  WORK: "work",
  REVIEW_FEEDBACK: "review_feedback",
  APPROVAL: "approval",
  DENIAL: "denial",
  SYSTEM_EVENT: "system_event",
} as const;

// Author type values
export const AUTHOR_TYPE = {
  AGENT: "agent",
  USER: "user",
  SYSTEM: "system",
} as const;

// Derived TypeScript types for use in function signatures and component props
export type TaskStatus = (typeof TASK_STATUS)[keyof typeof TASK_STATUS];
export type TrustLevel = (typeof TRUST_LEVEL)[keyof typeof TRUST_LEVEL];
export type AgentStatus = (typeof AGENT_STATUS)[keyof typeof AGENT_STATUS];
export type ActivityEventType =
  (typeof ACTIVITY_EVENT_TYPE)[keyof typeof ACTIVITY_EVENT_TYPE];
export type MessageType = (typeof MESSAGE_TYPE)[keyof typeof MESSAGE_TYPE];
export type AuthorType = (typeof AUTHOR_TYPE)[keyof typeof AUTHOR_TYPE];

// Status color mapping for Kanban board
export const STATUS_COLORS: Record<
  TaskStatus,
  { border: string; bg: string; text: string }
> = {
  inbox: {
    border: "border-l-violet-500",
    bg: "bg-violet-100 dark:bg-violet-950",
    text: "text-violet-700 dark:text-violet-300",
  },
  assigned: {
    border: "border-l-cyan-500",
    bg: "bg-cyan-100 dark:bg-cyan-950",
    text: "text-cyan-700 dark:text-cyan-300",
  },
  in_progress: {
    border: "border-l-blue-500",
    bg: "bg-blue-100 dark:bg-blue-950",
    text: "text-blue-700 dark:text-blue-300",
  },
  review: {
    border: "border-l-amber-500",
    bg: "bg-amber-100 dark:bg-amber-950",
    text: "text-amber-700 dark:text-amber-300",
  },
  done: {
    border: "border-l-green-500",
    bg: "bg-green-100 dark:bg-green-950",
    text: "text-green-700 dark:text-green-300",
  },
  retrying: {
    border: "border-l-amber-600",
    bg: "bg-amber-100 dark:bg-amber-950",
    text: "text-amber-700 dark:text-amber-300",
  },
  crashed: {
    border: "border-l-red-500",
    bg: "bg-red-100 dark:bg-red-950",
    text: "text-red-700 dark:text-red-300",
  },
  deleted: {
    border: "border-l-gray-400",
    bg: "bg-gray-100 dark:bg-gray-900",
    text: "text-gray-500 dark:text-gray-400",
  },
};

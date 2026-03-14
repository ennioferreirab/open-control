/**
 * Shared authoring contract for LLM-first authoring sessions.
 *
 * Defines canonical phases, graph patch types, and a parser that
 * converts the backend snake_case payload into frontend camelCase.
 */

export type AuthoringPhase = "discovery" | "proposal" | "refinement" | "approval";

export type AuthoringMode = "agent" | "squad";

/** Canonical phases accepted by both agent and squad wizards. */
export const CANONICAL_PHASES: readonly AuthoringPhase[] = [
  "discovery",
  "proposal",
  "refinement",
  "approval",
];

/** Type guard for canonical phases. */
export function isCanonicalPhase(value: unknown): value is AuthoringPhase {
  return CANONICAL_PHASES.includes(value as AuthoringPhase);
}

/** Agent graph patch — contains an agents array. */
export interface AgentGraphPatch {
  agents?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

/** Squad graph patch — structured with squad, agents, and workflows keys. */
export interface SquadGraphPatch {
  squad: { outcome: string; [key: string]: unknown };
  agents: Array<{ key: string; role: string; [key: string]: unknown }>;
  workflows: Array<{ key: string; steps: unknown[]; [key: string]: unknown }>;
}

/** Frontend-facing authoring response (camelCase). */
export interface AuthoringResponse<TPatch = Record<string, unknown>> {
  assistantMessage: string;
  phase: AuthoringPhase;
  draftGraphPatch: TPatch;
  unresolvedQuestions: string[];
  preview: Record<string, unknown>;
  readiness: number;
}

/** Raw backend payload shape (snake_case). */
interface RawAuthoringPayload {
  assistant_message?: unknown;
  phase?: unknown;
  draft_graph_patch?: unknown;
  unresolved_questions?: unknown;
  preview?: unknown;
  readiness?: unknown;
  mode?: unknown;
}

/**
 * Parse and validate a raw backend authoring payload into a typed
 * frontend AuthoringResponse. Throws if required fields are missing
 * or if the phase is not canonical.
 */
export function parseAuthoringResponse<TPatch = Record<string, unknown>>(
  raw: unknown,
): AuthoringResponse<TPatch> {
  const payload = raw as RawAuthoringPayload;

  if (typeof payload.assistant_message !== "string") {
    throw new Error(
      `Invalid authoring response: assistant_message must be a string, got ${typeof payload.assistant_message}`,
    );
  }

  const phase = payload.phase;
  if (!isCanonicalPhase(phase)) {
    throw new Error(
      `Invalid authoring response: phase ${String(phase)} is not canonical. ` +
        `Expected one of: ${CANONICAL_PHASES.join(", ")}`,
    );
  }

  const patch = (payload.draft_graph_patch ?? {}) as TPatch;
  const unresolvedQuestions = Array.isArray(payload.unresolved_questions)
    ? (payload.unresolved_questions as string[])
    : [];
  const preview =
    payload.preview && typeof payload.preview === "object"
      ? (payload.preview as Record<string, unknown>)
      : {};
  const readiness = typeof payload.readiness === "number" ? payload.readiness : 0;

  return {
    assistantMessage: payload.assistant_message,
    phase,
    draftGraphPatch: patch,
    unresolvedQuestions,
    preview,
    readiness,
  };
}

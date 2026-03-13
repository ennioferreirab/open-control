/**
 * Agent Spec V2 Compiler
 *
 * Pure, side-effect-free functions that compile structured `Agent Spec V2`
 * authoring sections into flat runtime-safe projection payloads.
 *
 * The compiler does NOT touch Convex, files, or any I/O. It only transforms
 * data structures. Projection metadata (`compiledFromSpecId`, etc.) is
 * injected by the caller.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Structured authoring input for an Agent Spec V2.
 * These fields are the authoring-layer truth and are compiled into the
 * runtime prompt and soul. They do NOT appear on the runtime `agents` record.
 */
export interface AgentSpecInput {
  /** Unique slug identifier for the agent. */
  name: string;
  /** Human-readable display name. */
  displayName: string;
  /** Short role description, used as the headline of the compiled prompt. */
  role: string;
  /** What this agent is responsible for (1–N bullet points). */
  responsibilities: string[];
  /** Things this agent explicitly does NOT do. */
  nonGoals?: string[];
  /** Core operating principles guiding decisions. */
  principles?: string[];
  /** Tone and communication style guidance. */
  voiceGuidance?: string;
  /** Behaviors to actively avoid. */
  antiPatterns?: string[];
  /** Expected output shape, format, and quality bar. */
  outputContract?: string;
  /** Which tools may be used and how. */
  toolPolicy?: string;
  /** Memory strategy or persistence rules. */
  memoryPolicy?: string;
  /** Skill names this agent should have in the runtime. */
  skills: string[];
  /** Optional model override for the agent. */
  model?: string;
  /** Optional explicit soul text. Generated from role if absent. */
  soul?: string;
  /** Optional interactive provider. */
  interactiveProvider?: string;
}

/**
 * Runtime projection payload written into the `agents` Convex table.
 * Authoring-only fields are compiled into `prompt` and `soul` — they do
 * not appear here.
 */
export interface AgentRuntimeProjection {
  name: string;
  displayName: string;
  role: string;
  prompt: string;
  soul: string;
  skills: string[];
  model?: string;
  interactiveProvider?: string;
  /** ID of the `agentSpecs` document this projection was compiled from. */
  compiledFromSpecId: string;
  /** Version of the spec at compile time. */
  compiledFromVersion: number;
  /** ISO 8601 timestamp when the projection was compiled. */
  compiledAt: string;
}

// ---------------------------------------------------------------------------
// Prompt compilation
// ---------------------------------------------------------------------------

/**
 * Compile an Agent Spec V2 into a flat runtime prompt string.
 *
 * Sections are assembled in a deterministic order and separated by blank lines.
 * Empty or absent sections are omitted entirely.
 */
export function compilePromptFromSpec(spec: AgentSpecInput): string {
  const sections: string[] = [];

  // Identity and role
  sections.push(`You are ${spec.displayName}, a ${spec.role}.`);

  // Responsibilities
  if (spec.responsibilities.length > 0) {
    sections.push("## Responsibilities\n" + spec.responsibilities.map((r) => `- ${r}`).join("\n"));
  }

  // Non-goals
  if (spec.nonGoals && spec.nonGoals.length > 0) {
    sections.push("## Not In Scope\n" + spec.nonGoals.map((g) => `- ${g}`).join("\n"));
  }

  // Principles
  if (spec.principles && spec.principles.length > 0) {
    sections.push("## Principles\n" + spec.principles.map((p) => `- ${p}`).join("\n"));
  }

  // Voice guidance / working style
  if (spec.voiceGuidance) {
    sections.push("## Working Style\n" + spec.voiceGuidance);
  }

  // Anti-patterns
  if (spec.antiPatterns && spec.antiPatterns.length > 0) {
    sections.push("## Anti-Patterns\n" + spec.antiPatterns.map((a) => `- Avoid: ${a}`).join("\n"));
  }

  // Tool policy
  if (spec.toolPolicy) {
    sections.push("## Tool Usage\n" + spec.toolPolicy);
  }

  // Memory policy
  if (spec.memoryPolicy) {
    sections.push("## Memory\n" + spec.memoryPolicy);
  }

  // Output contract
  if (spec.outputContract) {
    sections.push("## Output Contract\n" + spec.outputContract);
  }

  return sections.join("\n\n");
}

// ---------------------------------------------------------------------------
// Soul compilation
// ---------------------------------------------------------------------------

/**
 * Compile the runtime `soul` from an Agent Spec V2.
 *
 * If the spec already provides explicit soul text, it is returned as-is.
 * Otherwise a minimal soul is generated from the role description so the
 * runtime `soul` field is never empty.
 */
export function compileSoulFromSpec(spec: AgentSpecInput): string {
  if (spec.soul && spec.soul.trim().length > 0) {
    return spec.soul.trim();
  }
  // Generate a sensible default soul from the role so the field is never blank.
  return `You are a dedicated ${spec.role}. You bring expertise, care, and rigour to every task you take on.`;
}

// ---------------------------------------------------------------------------
// Full spec compilation
// ---------------------------------------------------------------------------

/**
 * Compile an Agent Spec V2 into a complete runtime projection payload.
 *
 * @param spec - The structured authoring input.
 * @param specId - The Convex document ID of the `agentSpecs` record.
 * @param specVersion - The version number of the spec at compile time.
 * @param compiledAt - Optional ISO 8601 timestamp to use as the compilation
 *   time. When provided (e.g. in tests), it is used as-is so the function
 *   remains deterministic. When omitted, `new Date().toISOString()` is called.
 * @returns A projection payload ready to be written into the `agents` table.
 */
export function compileAgentSpec(
  spec: AgentSpecInput,
  specId: string,
  specVersion: number,
  compiledAt?: string,
): AgentRuntimeProjection {
  const projection: AgentRuntimeProjection = {
    name: spec.name,
    displayName: spec.displayName,
    role: spec.role,
    prompt: compilePromptFromSpec(spec),
    soul: compileSoulFromSpec(spec),
    skills: spec.skills,
    compiledFromSpecId: specId,
    compiledFromVersion: specVersion,
    compiledAt: compiledAt ?? new Date().toISOString(),
  };

  if (spec.model !== undefined) {
    projection.model = spec.model;
  }

  if (spec.interactiveProvider !== undefined) {
    projection.interactiveProvider = spec.interactiveProvider;
  }

  return projection;
}

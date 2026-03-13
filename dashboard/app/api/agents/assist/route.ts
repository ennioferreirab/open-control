/**
 * DEPRECATED: /api/agents/assist
 *
 * This route previously generated raw YAML from a natural language description.
 * It has been retired in favour of the structured authoring wizard at:
 *
 *   POST /api/authoring/agent-wizard
 *
 * The new route returns a structured JSON response
 * { question, draft_patch, phase, readiness, summary_sections, recommended_next_phase }
 * instead of raw YAML, and drives the deep Create Agent wizard.
 *
 * This file is kept to avoid 404s from any cached references.  All new code
 * should target /api/authoring/agent-wizard directly.
 */

import { NextRequest, NextResponse } from "next/server";

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export async function POST(_req: NextRequest) {
  return NextResponse.json(
    {
      error: "This endpoint is retired. Use POST /api/authoring/agent-wizard instead.",
      redirect: "/api/authoring/agent-wizard",
    },
    { status: 410 },
  );
}

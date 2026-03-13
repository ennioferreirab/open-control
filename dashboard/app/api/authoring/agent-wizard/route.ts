import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import { writeFile, unlink } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";
import { randomUUID } from "crypto";

const execPromise = promisify(exec);

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface AgentWizardRequest {
  messages: ChatMessage[];
  current_spec: Record<string, unknown>;
  phase: string;
}

/**
 * POST /api/authoring/agent-wizard
 *
 * Returns a structured authoring response for the deep Create Agent wizard.
 * Never returns raw YAML — the response contract is:
 *   { question, draft_patch, phase, readiness, summary_sections, recommended_next_phase }
 */
export async function POST(request: NextRequest) {
  const tmpScript = join(tmpdir(), `nanobot-agent-wizard-${randomUUID()}.py`);
  const tmpInput = join(tmpdir(), `nanobot-agent-wizard-input-${randomUUID()}.json`);

  try {
    const body: AgentWizardRequest = await request.json();
    const messages: ChatMessage[] = body.messages || [];
    const currentSpec = body.current_spec || {};
    const phase = body.phase || "purpose";

    const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");

    if (!lastUserMessage) {
      return NextResponse.json({ error: "No user message found" }, { status: 400 });
    }

    await writeFile(
      tmpInput,
      JSON.stringify({ messages, current_spec: currentSpec, phase }),
      "utf-8",
    );

    const projectRoot = join(process.cwd(), "..");
    const pythonScript = `
import json
import asyncio
import sys

sys.path.insert(0, ${JSON.stringify(projectRoot)})

from mc.contexts.agents.authoring_assist import (
    AuthoringPhase,
    generate_agent_assist_response,
)
from nanobot.mc.provider_factory import create_provider

async def main():
    with open(${JSON.stringify(tmpInput)}, "r") as f:
        payload = json.load(f)

    messages = payload["messages"]
    current_spec = payload.get("current_spec", {})
    phase_str = payload.get("phase", "purpose")

    try:
        phase = AuthoringPhase(phase_str)
    except ValueError:
        phase = AuthoringPhase.PURPOSE

    try:
        provider, model = create_provider()
        result = await generate_agent_assist_response(
            provider=provider,
            messages=messages,
            current_spec=current_spec,
            phase=phase,
            model=model,
        )
        print(json.dumps(result.to_dict()))
    except Exception as e:
        from mc.contexts.agents.authoring_assist import (
            build_agent_question,
            compute_readiness,
            SpecDraftPatch,
        )
        question = build_agent_question(phase, current_spec)
        print(json.dumps({
            "question": question,
            "draft_patch": {"fields": {}},
            "phase": phase.value,
            "readiness": compute_readiness(current_spec),
            "summary_sections": {},
            "recommended_next_phase": phase.value,
            "_error": str(e),
        }))

asyncio.run(main())
`;

    await writeFile(tmpScript, pythonScript, "utf-8");

    try {
      const { stdout, stderr } = await execPromise(`uv run python ${JSON.stringify(tmpScript)}`, {
        cwd: projectRoot,
        timeout: 60000,
        env: { ...process.env, PYTHONPATH: projectRoot },
      });

      if (stderr) {
        console.error("Python stderr:", stderr);
      }

      await unlink(tmpScript).catch(() => {});
      await unlink(tmpInput).catch(() => {});

      const result = JSON.parse(stdout.trim());
      return NextResponse.json(result);
    } catch (error: unknown) {
      console.error("Python execution failed:", error);

      await unlink(tmpScript).catch(() => {});
      await unlink(tmpInput).catch(() => {});

      // Fallback: return a structured response so the UI can continue
      return NextResponse.json({
        question:
          "I'm unable to connect to the LLM right now. Please describe what you'd like this agent to do and I'll help guide you.",
        draft_patch: { fields: {} },
        phase: phase,
        readiness: 0,
        summary_sections: currentSpec,
        recommended_next_phase: phase,
      });
    }
  } catch (error) {
    console.error("Agent wizard failed:", error);
    await unlink(tmpScript).catch(() => {});
    return NextResponse.json({ error: "Failed to process request" }, { status: 500 });
  }
}

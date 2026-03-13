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

interface SquadWizardRequest {
  messages: ChatMessage[];
  current_spec: Record<string, unknown>;
  phase: string;
}

/**
 * POST /api/authoring/squad-wizard
 *
 * Returns a structured authoring response for the deep Create Squad wizard.
 * Never returns raw YAML — the response contract is:
 *   { question, draft_patch, phase, readiness, summary_sections, recommended_next_phase }
 *
 * Squad phases: team_design -> workflow_design -> review_design -> approval
 */
export async function POST(request: NextRequest) {
  const tmpScript = join(tmpdir(), `nanobot-squad-wizard-${randomUUID()}.py`);
  const tmpInput = join(tmpdir(), `nanobot-squad-wizard-input-${randomUUID()}.json`);

  try {
    const body: SquadWizardRequest = await request.json();
    const messages: ChatMessage[] = body.messages || [];
    const currentSpec = body.current_spec || {};
    const phase = body.phase || "team_design";

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

from mc.contexts.agents.authoring_assist import generate_squad_assist_response
from nanobot.mc.provider_factory import create_provider

async def main():
    with open(${JSON.stringify(tmpInput)}, "r") as f:
        payload = json.load(f)

    messages = payload["messages"]
    current_spec = payload.get("current_spec", {})
    phase = payload.get("phase", "team_design")

    try:
        provider, model = create_provider()
        result = await generate_squad_assist_response(
            provider=provider,
            messages=messages,
            current_spec=current_spec,
            phase=phase,
            model=model,
        )
        print(json.dumps(result))
    except Exception as e:
        from mc.contexts.agents.authoring_assist import (
            build_squad_question,
            advance_squad_phase,
        )
        question = build_squad_question(phase, current_spec)
        squad_keys = ["team_design", "workflow_design", "review_design"]
        filled = sum(1 for k in squad_keys if (current_spec.get(k) or "").strip())
        readiness = filled / len(squad_keys)
        print(json.dumps({
            "question": question,
            "draft_patch": {"fields": {}},
            "phase": phase,
            "readiness": readiness,
            "summary_sections": {},
            "recommended_next_phase": phase,
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
          "I'm unable to connect to the LLM right now. Please describe your squad design and I'll help guide you.",
        draft_patch: { fields: {} },
        phase: phase,
        readiness: 0,
        summary_sections: currentSpec,
        recommended_next_phase: phase,
      });
    }
  } catch (error) {
    console.error("Squad wizard failed:", error);
    await unlink(tmpScript).catch(() => {});
    return NextResponse.json({ error: "Failed to process request" }, { status: 500 });
  }
}

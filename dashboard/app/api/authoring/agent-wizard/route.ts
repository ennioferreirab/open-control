import { exec } from "child_process";
import { unlink, writeFile } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import { promisify } from "util";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { randomUUID } from "crypto";
import { CANONICAL_PHASES } from "@/features/agents/lib/authoringContract";

const CANONICAL_PHASE_SET = new Set(CANONICAL_PHASES);

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export async function POST(request: NextRequest) {
  const tmpScript = join(tmpdir(), `authoring-agent-${randomUUID()}.py`);
  const tmpInput = join(tmpdir(), `authoring-agent-input-${randomUUID()}.json`);

  try {
    const body = await request.json();
    const messages: ChatMessage[] = body.messages ?? [];
    const phase: string = body.phase ?? "discovery";

    const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUserMessage) {
      return NextResponse.json({ error: "No user message found" }, { status: 400 });
    }

    if (!CANONICAL_PHASE_SET.has(phase as never)) {
      return NextResponse.json(
        {
          error: `Invalid phase "${phase}". Must be one of: ${CANONICAL_PHASES.join(", ")}`,
        },
        { status: 400 },
      );
    }

    const projectRoot = join(process.cwd(), "..");
    await writeFile(tmpInput, JSON.stringify({ messages, phase }), "utf-8");

    const pythonScript = `
import json
import asyncio
import sys

sys.path.insert(0, ${JSON.stringify(projectRoot)})

from mc.contexts.agents.authoring_assist import build_agent_authoring_response
from mc.infrastructure.providers.factory import create_provider

async def main():
    with open(${JSON.stringify(tmpInput)}, "r") as f:
        payload = json.load(f)

    messages = payload["messages"]
    phase = payload["phase"]

    try:
        provider, _model = create_provider()
        result = await build_agent_authoring_response(
            provider=provider,
            messages=messages,
            current_phase=phase,
        )
        print(json.dumps(result.to_dict()))
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        fallback = {
            "assistant_message": f"Error generating response: {e}",
            "phase": phase,
            "draft_graph_patch": {},
            "unresolved_questions": [],
            "preview": {},
            "readiness": 0.0,
            "mode": "agent",
        }
        print(json.dumps(fallback))

asyncio.run(main())
`;

    await writeFile(tmpScript, pythonScript, "utf-8");

    const execPromise = promisify(exec);

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

      return NextResponse.json({
        assistant_message: "I'm unable to connect to the LLM right now. Please try again later.",
        phase,
        draft_graph_patch: {},
        unresolved_questions: [],
        preview: {},
        readiness: 0.0,
        mode: "agent",
      });
    }
  } catch (error) {
    console.error("Agent authoring wizard failed:", error);
    await unlink(tmpScript).catch(() => {});
    return NextResponse.json({ error: "Failed to process request" }, { status: 500 });
  }
}

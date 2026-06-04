/**
 * DEPRECATED: /api/agents/assist
 *
 * This route previously generated raw YAML from a natural language description.
 * It is still functional to avoid breaking CreateAgentSheet.tsx (Chat tab).
 * New code should target /api/authoring/agent-wizard instead, which returns a
 * structured JSON response suitable for the deep Create Agent wizard.
 *
 * A Deprecation header is sent on every response so callers can detect the
 * transition.  The route will be removed once CreateAgentSheet is retired.
 */

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

export async function POST(request: NextRequest) {
  const tmpScript = join(tmpdir(), `oc-assist-${randomUUID()}.py`);

  try {
    const body = await request.json();
    const messages: ChatMessage[] = body.messages || [];

    // Extract the last user message as the description
    const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");

    if (!lastUserMessage) {
      return NextResponse.json({ error: "No user message found" }, { status: 400 });
    }

    // Build the input payload as a JSON file to avoid shell escaping issues
    const tmpInput = join(tmpdir(), `oc-assist-input-${randomUUID()}.json`);
    await writeFile(
      tmpInput,
      JSON.stringify({ messages, description: lastUserMessage.content }),
      "utf-8",
    );

    // Write a Python script to a temp file to avoid shell escaping issues
    const projectRoot = join(process.cwd(), "..");
    const pythonScript = `
import json
import asyncio
import sys

sys.path.insert(0, ${JSON.stringify(projectRoot)})

from mc.cli.agent_assist import (
    extract_yaml_from_response,
    validate_yaml_content,
    generate_agent_yaml,
)

async def main():
    with open(${JSON.stringify(tmpInput)}, "r") as f:
        payload = json.load(f)

    description = payload["description"]
    messages = payload["messages"]

    # Build feedback from conversation if this isn't the first message
    feedback = None
    if len(messages) > 2:
        prior_exchanges = []
        for m in messages[:-1]:
            if m["role"] == "user":
                prior_exchanges.append(m["content"])
        if len(prior_exchanges) > 1:
            feedback = "; ".join(prior_exchanges[:-1])

    try:
        raw = await generate_agent_yaml(description, feedback=feedback)
        if not raw or not raw.strip():
            print(json.dumps({"message": "I couldn't generate a configuration. Could you describe the agent in more detail?", "yaml": None}))
            return

        yaml_text = extract_yaml_from_response(raw)
        parsed, errors = validate_yaml_content(yaml_text)

        if errors:
            error_lines = "\\n".join(f"- {e}" for e in errors)
            error_msg = f"I generated a configuration but it has some issues:\\n{error_lines}\\n\\nCould you provide more details so I can fix these?"
            print(json.dumps({"message": error_msg, "yaml": None}))
            return

        agent_name = parsed.get("name", "unnamed-agent")
        agent_role = parsed.get("role", "Agent")

        message = f"I've generated a configuration for **{agent_name}** ({agent_role}). Review the YAML below \\u2014 you can accept it, request changes, or cancel."
        print(json.dumps({"message": message, "yaml": yaml_text}))

    except Exception as e:
        print(json.dumps({"message": f"Error generating agent: {e}", "yaml": None}))

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

      // Clean up temp files
      await unlink(tmpScript).catch(() => {});
      await unlink(tmpInput).catch(() => {});

      const result = JSON.parse(stdout.trim());
      return NextResponse.json(result, {
        headers: {
          Deprecation: "true",
          Link: '</api/authoring/agent-wizard>; rel="successor-version"',
        },
      });
    } catch (error: unknown) {
      console.error("Python execution failed:", error);

      // Clean up temp files
      await unlink(tmpScript).catch(() => {});
      await unlink(tmpInput).catch(() => {});

      // Fallback: provide guidance without LLM
      return NextResponse.json(
        {
          message:
            "I'm unable to connect to the LLM right now. You can use the Form tab to create an agent manually, or try again later.",
          yaml: null,
        },
        {
          headers: {
            Deprecation: "true",
            Link: '</api/authoring/agent-wizard>; rel="successor-version"',
          },
        },
      );
    }
  } catch (error) {
    console.error("Agent assist failed:", error);
    await unlink(tmpScript).catch(() => {});
    return NextResponse.json({ error: "Failed to process request" }, { status: 500 });
  }
}

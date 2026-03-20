import { NextRequest, NextResponse } from "next/server";
import { readFile, writeFile, mkdir } from "fs/promises";
import { dirname } from "path";
import yaml from "js-yaml";
import { getRuntimePath } from "@/lib/runtimeHome";

const AGENT_NAME_RE = /^[a-zA-Z0-9_-]+$/;

type AgentConfig = {
  name: string;
  role?: string;
  prompt?: string;
  model?: string;
  display_name?: string;
  skills?: string[];
  soul?: string;
  claude_code?: {
    permission_mode?: string;
    max_budget_usd?: number | null;
    max_turns?: number | null;
  } | null;
};

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ agentName: string }> },
) {
  const { agentName } = await params;

  if (!AGENT_NAME_RE.test(agentName)) {
    return NextResponse.json({ error: "Invalid agentName" }, { status: 400 });
  }

  let updates: Partial<AgentConfig>;
  try {
    updates = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const configPath = getRuntimePath("agents", agentName, "config.yaml");

  // Read existing config to preserve fields not being updated
  let existing: AgentConfig = { name: agentName };
  try {
    const raw = await readFile(configPath, "utf-8");
    existing = (yaml.load(raw) as AgentConfig) ?? { name: agentName };
  } catch {
    // File may not exist yet — start fresh
  }

  // Merge updates into existing config
  const merged: AgentConfig = { ...existing };
  if (updates.role !== undefined) merged.role = updates.role;
  if (updates.prompt !== undefined) merged.prompt = updates.prompt;
  if (updates.model !== undefined) merged.model = updates.model || undefined;
  if (updates.display_name !== undefined) merged.display_name = updates.display_name;
  if (updates.skills !== undefined) merged.skills = updates.skills;
  if (updates.soul !== undefined) merged.soul = updates.soul || undefined;
  if (updates.claude_code !== undefined) {
    if (updates.claude_code === null) {
      delete merged.claude_code;
    } else {
      const cc: Record<string, unknown> = {};
      if (updates.claude_code.permission_mode)
        cc.permission_mode = updates.claude_code.permission_mode;
      if (updates.claude_code.max_budget_usd != null)
        cc.max_budget_usd = updates.claude_code.max_budget_usd;
      if (updates.claude_code.max_turns != null) cc.max_turns = updates.claude_code.max_turns;
      merged.claude_code = cc as AgentConfig["claude_code"];
    }
  }

  // Remove undefined keys before serializing
  const clean = Object.fromEntries(
    Object.entries(merged).filter(([, v]) => v !== undefined && v !== null),
  );

  try {
    await mkdir(dirname(configPath), { recursive: true });
    await writeFile(configPath, yaml.dump(clean, { lineWidth: -1, noRefs: true }), "utf-8");
    return new NextResponse(null, { status: 204 });
  } catch {
    return NextResponse.json({ error: "Failed to write config" }, { status: 500 });
  }
}

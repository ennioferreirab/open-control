import { NextRequest, NextResponse } from "next/server";
import { readFile, writeFile, mkdir } from "fs/promises";
import { join, dirname } from "path";
import { homedir } from "os";
import yaml from "js-yaml";

const AGENT_NAME_RE = /^[a-zA-Z0-9_-]+$/;

type AgentConfig = {
  name: string;
  role?: string;
  prompt?: string;
  model?: string;
  display_name?: string;
  skills?: string[];
  soul?: string;
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

  const configPath = join(homedir(), ".nanobot", "agents", agentName, "config.yaml");

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
  if (updates.skills !== undefined) merged.skills = updates.skills?.length ? updates.skills : undefined;
  if (updates.soul !== undefined) merged.soul = updates.soul || undefined;

  // Remove undefined keys before serializing
  const clean = Object.fromEntries(
    Object.entries(merged).filter(([, v]) => v !== undefined && v !== null)
  );

  try {
    await mkdir(dirname(configPath), { recursive: true });
    await writeFile(configPath, yaml.dump(clean, { lineWidth: -1, noRefs: true }), "utf-8");
    return new NextResponse(null, { status: 204 });
  } catch {
    return NextResponse.json({ error: "Failed to write config" }, { status: 500 });
  }
}

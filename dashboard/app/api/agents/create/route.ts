import { NextRequest, NextResponse } from "next/server";
import { writeFile, mkdir } from "fs/promises";
import { join } from "path";
import { getRuntimePath } from "@/lib/runtimeHome";

interface AgentConfig {
  name: string;
  display_name?: string;
  displayName?: string;
  role: string;
  prompt: string;
  skills?: string[];
  model?: string;
}

function toYaml(config: AgentConfig): string {
  const lines: string[] = [];
  lines.push(`name: ${config.name}`);

  const dn = config.display_name || config.displayName;
  if (dn) {
    lines.push(`display_name: "${dn}"`);
  }

  lines.push(`role: "${config.role}"`);

  // Use literal block scalar for prompt
  lines.push("prompt: |");
  for (const line of config.prompt.split("\n")) {
    lines.push(`  ${line}`);
  }

  if (config.skills && config.skills.length > 0) {
    lines.push("skills:");
    for (const skill of config.skills) {
      lines.push(`  - ${skill}`);
    }
  }

  if (config.model) {
    lines.push(`model: ${config.model}`);
  }

  return lines.join("\n") + "\n";
}

function parseSimpleYaml(yaml: string): AgentConfig {
  const result: Record<string, unknown> = {};
  let currentKey = "";
  let blockValue: string[] = [];
  let inBlock = false;
  let listKey = "";
  let listValues: string[] = [];

  for (const line of yaml.split("\n")) {
    // Handle block scalar continuation
    if (inBlock) {
      if (line.startsWith("  ") && !line.match(/^[a-z_]+:/)) {
        blockValue.push(line.slice(2));
        continue;
      } else {
        result[currentKey] = blockValue.join("\n").trimEnd();
        inBlock = false;
        blockValue = [];
      }
    }

    // Handle list continuation
    if (listKey && line.startsWith("  - ")) {
      listValues.push(line.slice(4).trim());
      continue;
    } else if (listKey) {
      result[listKey] = listValues;
      listKey = "";
      listValues = [];
    }

    const match = line.match(/^([a-z_]+):\s*(.*)/);
    if (!match) continue;

    const [, key, value] = match;

    if (value === "|") {
      currentKey = key;
      inBlock = true;
      blockValue = [];
    } else if (value === "") {
      // Could be start of a list
      listKey = key;
      listValues = [];
    } else if (value.startsWith("[") && value.endsWith("]")) {
      result[key] = value
        .slice(1, -1)
        .split(",")
        .map((s) => s.trim().replace(/^['"]|['"]$/g, ""))
        .filter(Boolean);
    } else {
      result[key] = value.replace(/^['"]|['"]$/g, "");
    }
  }

  // Flush remaining
  if (inBlock) result[currentKey] = blockValue.join("\n").trimEnd();
  if (listKey) result[listKey] = listValues;

  return result as unknown as AgentConfig;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    let config: AgentConfig;

    if (body.yaml) {
      // Legacy YAML path (kept for backward compatibility)
      config = parseSimpleYaml(body.yaml);
    } else if (body.specId) {
      // Spec-projection path: the spec has already been compiled; just write the files
      config = {
        name: body.name,
        role: body.role,
        prompt: body.prompt,
        skills: body.skills,
        model: body.model,
        display_name: body.displayName,
      };
    } else {
      // Form/wizard mode: build config from fields
      config = {
        name: body.name,
        role: body.role,
        prompt: body.prompt,
        skills: body.skills,
        model: body.model,
      };

      // Only include display_name if explicitly provided and different from auto-generated
      const autoDisplayName = body.name
        ?.split("-")
        .map((w: string) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");

      if (body.displayName && body.displayName !== autoDisplayName) {
        config.display_name = body.displayName;
      }
    }

    if (!config.name || !config.role || !config.prompt) {
      return NextResponse.json({ error: "name, role, and prompt are required" }, { status: 400 });
    }

    // Validate name pattern
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(config.name)) {
      return NextResponse.json(
        { error: "Invalid agent name. Use lowercase letters, numbers, and hyphens." },
        { status: 400 },
      );
    }

    const yamlText = toYaml(config);

    // Write to the configured runtime home agents directory.
    const agentDir = getRuntimePath("agents", config.name);
    await mkdir(join(agentDir, "memory"), { recursive: true });
    await mkdir(join(agentDir, "skills"), { recursive: true });
    await writeFile(join(agentDir, "config.yaml"), yamlText, "utf-8");

    // Generate SOUL.md if not already present
    const soulPath = join(agentDir, "SOUL.md");
    try {
      const { readFile } = await import("fs/promises");
      await readFile(soulPath);
    } catch {
      // File doesn't exist — generate default soul
      const displayName =
        config.display_name ||
        config.displayName ||
        config.name
          .split("-")
          .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
          .join(" ");

      const soulContent = `# Soul

I am ${displayName}, an Open Control agent.

## Role
${config.role}

## Personality
- Helpful and focused on my area of expertise
- Concise and to the point
- Proactive in identifying relevant details

## Values
- Accuracy over speed
- Transparency in actions
- Collaboration with the team

## Communication Style
- Be clear and direct
- Explain reasoning when helpful
- Ask clarifying questions when needed
`;
      await writeFile(soulPath, soulContent, "utf-8");
    }

    return NextResponse.json({ success: true, config });
  } catch (error) {
    console.error("Agent creation failed:", error);
    return NextResponse.json({ error: "Failed to create agent" }, { status: 500 });
  }
}

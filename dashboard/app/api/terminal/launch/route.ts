import { NextRequest, NextResponse } from "next/server";
import { execFile, spawn } from "child_process";
import { writeFileSync } from "fs";
import { resolve, join } from "path";

const PROJECT_ROOT = resolve(process.cwd(), "..");

/**
 * Generate a temporary .mcp.json that connects to the running MC gateway
 * via its Unix socket. This gives the Claude Code TUI access to MC tools
 * like create_agent_spec and publish_squad_graph.
 */
function ensureMcpConfig(): string {
  const configPath = "/tmp/mc-authoring-mcp.json";
  const port = process.env.PORT || "3000";
  const scriptPath = join(PROJECT_ROOT, "dashboard", "scripts", "mcp-specs-server.mjs");
  const config = {
    mcpServers: {
      mc: {
        command: process.execPath,
        args: [scriptPath],
        env: {
          MC_API_BASE: `http://localhost:${port}`,
          PATH: process.env.PATH,
          HOME: process.env.HOME,
        },
      },
    },
  };
  writeFileSync(configPath, JSON.stringify(config, null, 2));
  return configPath;
}

function buildClaudeCommand(prompt: string): string {
  const mcpConfigPath = ensureMcpConfig();
  const parts = [
    "cd",
    PROJECT_ROOT,
    "&&",
    "claude",
    "--effort",
    "high",
    "--dangerously-skip-permissions",
    "--mcp-config",
    mcpConfigPath,
    "--",
  ];
  parts.push(`'${prompt.replace(/'/g, "'\\''")}'`);
  return parts.join(" ");
}

function openTerminalMac(cmd: string): void {
  execFile(
    "osascript",
    [
      "-e",
      `tell application "Terminal" to activate`,
      "-e",
      `tell application "Terminal" to do script "${cmd}"`,
    ],
    (error) => {
      if (error) console.error("Failed to open terminal (macOS):", error);
    },
  );
}

function openTerminalLinux(cmd: string): void {
  const terminals = [
    { bin: "x-terminal-emulator", args: ["-e", `bash -c '${cmd}'`] },
    { bin: "gnome-terminal", args: ["--", "bash", "-c", cmd] },
    { bin: "konsole", args: ["-e", "bash", "-c", cmd] },
    { bin: "xfce4-terminal", args: ["-e", `bash -c '${cmd}'`] },
    { bin: "xterm", args: ["-e", `bash -c '${cmd}'`] },
  ];

  for (const term of terminals) {
    try {
      const child = spawn(term.bin, term.args, { detached: true, stdio: "ignore" });
      child.unref();
      return;
    } catch {
      continue;
    }
  }
  console.error("Failed to open terminal (Linux): no terminal emulator found");
}

function openTerminalWindows(cmd: string): void {
  spawn("cmd", ["/c", "start", "", "wt", "-d", PROJECT_ROOT, "cmd", "/k", cmd], {
    detached: true,
    stdio: "ignore",
    shell: true,
  }).on("error", () => {
    spawn("cmd", ["/c", "start", "cmd", "/k", cmd], {
      detached: true,
      stdio: "ignore",
      shell: true,
    }).unref();
  });
}

export async function POST(request: NextRequest) {
  try {
    const { prompt } = await request.json();

    if (!prompt || typeof prompt !== "string") {
      return NextResponse.json({ error: "prompt is required" }, { status: 400 });
    }

    const cmd = buildClaudeCommand(prompt);
    console.log("[terminal/launch] command:", cmd);

    switch (process.platform) {
      case "darwin":
        openTerminalMac(cmd);
        break;
      case "linux":
        openTerminalLinux(cmd);
        break;
      case "win32":
        openTerminalWindows(cmd);
        break;
      default:
        return NextResponse.json(
          { error: `Unsupported platform: ${process.platform}` },
          { status: 400 },
        );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Terminal launch failed:", error);
    return NextResponse.json({ error: "Failed to launch terminal" }, { status: 500 });
  }
}

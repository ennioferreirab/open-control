import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { getRuntimePath } from "@/lib/runtimeHome";

export async function GET() {
  const configPath = getRuntimePath("config.json");
  try {
    const content = await readFile(configPath, "utf-8");
    const config = JSON.parse(content) as {
      channels?: Record<string, { enabled?: boolean }>;
    };

    const channels = config.channels ?? {};
    const enabled = Object.entries(channels)
      .filter(([, cfg]) => cfg.enabled === true)
      .map(([name]) => name);

    // MC is always available as a channel option
    if (!enabled.includes("mc")) {
      enabled.push("mc");
    }

    return NextResponse.json({ channels: enabled });
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return NextResponse.json({ channels: ["mc"] });
    }
    return NextResponse.json({ error: "Failed to read config" }, { status: 500 });
  }
}

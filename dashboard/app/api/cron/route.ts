import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { join } from "path";
import { homedir } from "os";

type RawJob = Record<string, unknown>;

function normalizeJob(raw: RawJob): RawJob {
  // Already new format — has nested schedule/payload/state
  if (raw.schedule && raw.payload && raw.state) return raw;

  // Legacy flat format: { id, cron_expr, tz, message, created_at, enabled }
  const createdAtMs =
    typeof raw.createdAtMs === "number"
      ? raw.createdAtMs
      : raw.created_at
        ? new Date(raw.created_at as string).getTime()
        : 0;

  return {
    id: raw.id,
    name: raw.name ?? raw.id,
    enabled: raw.enabled ?? true,
    schedule: {
      kind: "cron",
      expr: raw.cron_expr ?? null,
      tz: raw.tz ?? null,
      atMs: null,
      everyMs: null,
    },
    payload: {
      kind: "agent_turn",
      message: raw.message ?? "",
      deliver: false,
      channel: null,
      to: null,
    },
    state: {
      nextRunAtMs: null,
      lastRunAtMs: null,
      lastStatus: null,
      lastError: null,
    },
    createdAtMs,
    updatedAtMs: raw.updatedAtMs ?? 0,
    deleteAfterRun: raw.deleteAfterRun ?? false,
  };
}

export async function GET() {
  const storePath = join(homedir(), ".nanobot", "cron", "jobs.json");
  try {
    const content = await readFile(storePath, "utf-8");
    if (!content.trim()) return NextResponse.json({ jobs: [] });
    const data = JSON.parse(content) as { version?: number; jobs?: RawJob[] };
    const jobs = (data.jobs ?? []).map(normalizeJob);
    return NextResponse.json({ jobs });
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return NextResponse.json({ jobs: [] });
    }
    return NextResponse.json(
      { error: "Failed to read cron jobs" },
      { status: 500 },
    );
  }
}

import { NextRequest, NextResponse } from "next/server";
import { readFile, writeFile, rename, unlink } from "fs/promises";
import { join } from "path";
import { homedir } from "os";

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await params;
  const storePath = join(homedir(), ".nanobot", "cron", "jobs.json");
  const tmpPath = `${storePath}.tmp`;

  try {
    const content = await readFile(storePath, "utf-8");
    if (!content.trim()) {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }

    const data = JSON.parse(content) as { version?: number; jobs?: { id: string }[] };
    const jobs = data.jobs ?? [];
    const filtered = jobs.filter((j) => j.id !== jobId);
    if (filtered.length === jobs.length) {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }

    const updated = JSON.stringify({ ...data, jobs: filtered }, null, 2);
    await writeFile(tmpPath, updated, "utf-8");
    await rename(tmpPath, storePath);

    return NextResponse.json({ success: true });
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }
    try {
      await unlink(tmpPath);
    } catch {}
    return NextResponse.json({ error: "Failed to delete cron job" }, { status: 500 });
  }
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await params;
  const storePath = join(homedir(), ".nanobot", "cron", "jobs.json");
  const tmpPath = `${storePath}.tmp`;

  let body: { channel?: string | null; to?: string | null };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  try {
    const content = await readFile(storePath, "utf-8");
    if (!content.trim()) {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }

    const data = JSON.parse(content) as {
      version?: number;
      jobs?: Array<{
        id: string;
        payload?: {
          kind?: string;
          message?: string;
          deliver?: boolean;
          channel?: string | null;
          to?: string | null;
          taskId?: string | null;
        };
        updatedAtMs?: number;
        [key: string]: unknown;
      }>;
    };
    const jobs = data.jobs ?? [];
    const job = jobs.find((j) => j.id === jobId);
    if (!job) {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }

    if (!job.payload) {
      job.payload = { kind: "agent_turn", message: "", deliver: false, channel: null, to: null, taskId: null };
    }
    if ("channel" in body) job.payload.channel = body.channel ?? null;
    if ("to" in body) job.payload.to = body.to ?? null;
    job.updatedAtMs = Date.now();

    const updated = JSON.stringify(data, null, 2);
    await writeFile(tmpPath, updated, "utf-8");
    await rename(tmpPath, storePath);

    return NextResponse.json({ success: true, job });
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }
    try {
      await unlink(tmpPath);
    } catch {}
    return NextResponse.json(
      { error: "Failed to update cron job" },
      { status: 500 },
    );
  }
}

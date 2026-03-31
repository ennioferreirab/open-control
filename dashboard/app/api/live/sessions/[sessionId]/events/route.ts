import { readFile } from "fs/promises";
import { NextRequest, NextResponse } from "next/server";

import { isValidLiveSessionId } from "@/lib/liveSessionFiles";
import { findLiveSessionPaths } from "@/lib/liveSessionFiles.server";

function parseAfterSeq(request: NextRequest): number {
  const value = request.nextUrl.searchParams.get("afterSeq");
  if (value === null || value === "") {
    return 0;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new Error("Invalid afterSeq");
  }
  return Math.floor(parsed);
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params;
  if (!isValidLiveSessionId(sessionId)) {
    return NextResponse.json({ error: "Invalid sessionId" }, { status: 400 });
  }

  let afterSeq: number;
  try {
    afterSeq = parseAfterSeq(request);
  } catch {
    return NextResponse.json({ error: "Invalid afterSeq" }, { status: 400 });
  }

  const paths = await findLiveSessionPaths(sessionId);
  if (!paths) {
    return NextResponse.json({ error: "Transcript not found" }, { status: 404 });
  }

  try {
    const contents = await readFile(paths.eventsPath, "utf-8");
    const events = contents
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line))
      .filter((event) => Number(event.seq ?? 0) > afterSeq);
    return NextResponse.json({ events });
  } catch (error: unknown) {
    const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
    if (code === "ENOENT") {
      return NextResponse.json({ error: "Transcript not found" }, { status: 404 });
    }
    return NextResponse.json({ error: "Failed to read live session events" }, { status: 500 });
  }
}

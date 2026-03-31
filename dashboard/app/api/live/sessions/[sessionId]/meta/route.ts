import { readFile } from "fs/promises";
import { NextRequest, NextResponse } from "next/server";

import { isValidLiveSessionId } from "@/lib/liveSessionFiles";
import { findLiveSessionPaths } from "@/lib/liveSessionFiles.server";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params;
  if (!isValidLiveSessionId(sessionId)) {
    return NextResponse.json({ error: "Invalid sessionId" }, { status: 400 });
  }

  const paths = await findLiveSessionPaths(sessionId);
  if (!paths) {
    return NextResponse.json({ error: "Transcript not found" }, { status: 404 });
  }

  try {
    const meta = JSON.parse(await readFile(paths.metaPath, "utf-8"));
    return NextResponse.json(meta);
  } catch (error: unknown) {
    const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
    if (code === "ENOENT") {
      return NextResponse.json({ error: "Transcript not found" }, { status: 404 });
    }
    return NextResponse.json({ error: "Failed to read live session metadata" }, { status: 500 });
  }
}

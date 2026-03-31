import { readFile } from "fs/promises";

import {
  type LiveSessionFilePaths,
  type LiveSessionIndex,
  getLiveSessionIndexPath,
  resolveLiveSessionPaths,
} from "@/lib/liveSessionFiles";

export async function readLiveSessionIndex(sessionId: string): Promise<LiveSessionIndex> {
  const filePath = getLiveSessionIndexPath(sessionId);
  return JSON.parse(await readFile(filePath, "utf-8")) as LiveSessionIndex;
}

export async function findLiveSessionPaths(
  sessionId: string,
): Promise<LiveSessionFilePaths | null> {
  try {
    const index = await readLiveSessionIndex(sessionId);
    return resolveLiveSessionPaths(sessionId, index.taskId, index.stepId);
  } catch {
    return null;
  }
}

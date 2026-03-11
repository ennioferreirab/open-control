import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { join } from "path";
import { homedir } from "os";

export async function GET() {
  const path = join(homedir(), ".nanobot", "mc", "agent-orientation.md");

  try {
    const prompt = (await readFile(path, "utf-8")).trim();
    return NextResponse.json({ prompt });
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return NextResponse.json({ prompt: "" });
    }

    return NextResponse.json(
      { error: "Failed to read global orientation default" },
      { status: 500 },
    );
  }
}

import { NextRequest, NextResponse } from "next/server";
import { mkdir, rename, rm, unlink, writeFile } from "fs/promises";
import { basename, join } from "path";
import { getRuntimePath } from "@/lib/runtimeHome";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const TASK_ID_RE = /^[a-zA-Z0-9_-]+$/;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await params;

  if (!TASK_ID_RE.test(taskId)) {
    return NextResponse.json(
      { error: "Invalid taskId: only alphanumeric, - and _ are allowed" },
      { status: 400 },
    );
  }

  const attachmentsDir = getRuntimePath("tasks", taskId, "attachments");

  await mkdir(attachmentsDir, { recursive: true });

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json({ error: "Failed to parse multipart form data" }, { status: 400 });
  }

  const uploadedFiles: {
    name: string;
    type: string;
    size: number;
    subfolder: string;
    uploadedAt: string;
  }[] = [];

  for (const [, value] of formData.entries()) {
    if (!(value instanceof File)) continue;

    const file = value;
    if (file.size > MAX_FILE_SIZE) {
      return NextResponse.json(
        { error: `File "${file.name}" exceeds 10MB limit` },
        { status: 413 },
      );
    }
    // Sanitize the filename to prevent path traversal attacks: strip any
    // directory components so that e.g. "../../etc/passwd" becomes "passwd".
    const safeName = basename(file.name);
    if (!safeName) continue;

    const finalPath = join(attachmentsDir, safeName);
    const tmpPath = `${finalPath}.tmp`;

    const buffer = Buffer.from(await file.arrayBuffer());

    try {
      await writeFile(tmpPath, buffer);
      await rename(tmpPath, finalPath);
    } catch {
      await rm(tmpPath, { force: true });
      return NextResponse.json({ error: `Failed to write file: ${safeName}` }, { status: 500 });
    }

    uploadedFiles.push({
      name: safeName,
      type: file.type,
      size: file.size,
      subfolder: "attachments",
      uploadedAt: new Date().toISOString(),
    });
  }

  return NextResponse.json({ files: uploadedFiles });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await params;

  if (!TASK_ID_RE.test(taskId)) {
    return NextResponse.json({ error: "Invalid taskId" }, { status: 400 });
  }

  let body: { subfolder: string; filename: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { subfolder, filename } = body;

  if (typeof subfolder !== "string" || typeof filename !== "string") {
    return NextResponse.json({ error: "Missing or invalid subfolder/filename" }, { status: 400 });
  }

  if (subfolder !== "attachments") {
    return NextResponse.json({ error: "Only attachments can be deleted" }, { status: 403 });
  }

  const safeName = basename(filename);
  if (!safeName || safeName !== filename) {
    return NextResponse.json({ error: "Invalid filename" }, { status: 400 });
  }

  const filePath = getRuntimePath("tasks", taskId, "attachments", safeName);

  try {
    await unlink(filePath);
  } catch (err: unknown) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "ENOENT") {
      // Already gone — treat as success
      return NextResponse.json({ ok: true });
    }
    return NextResponse.json({ error: "Failed to delete file" }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}

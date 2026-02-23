import { NextRequest, NextResponse } from "next/server";
import { mkdir, rename, rm, writeFile } from "fs/promises";
import { join } from "path";
import { homedir } from "os";

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

  const attachmentsDir = join(
    homedir(),
    ".nanobot",
    "tasks",
    taskId,
    "attachments",
  );

  await mkdir(attachmentsDir, { recursive: true });

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json(
      { error: "Failed to parse multipart form data" },
      { status: 400 },
    );
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
    const finalPath = join(attachmentsDir, file.name);
    const tmpPath = `${finalPath}.tmp`;

    const buffer = Buffer.from(await file.arrayBuffer());

    try {
      await writeFile(tmpPath, buffer);
      await rename(tmpPath, finalPath);
    } catch (err) {
      await rm(tmpPath, { force: true });
      return NextResponse.json(
        { error: `Failed to write file: ${file.name}` },
        { status: 500 },
      );
    }

    uploadedFiles.push({
      name: file.name,
      type: file.type,
      size: file.size,
      subfolder: "attachments",
      uploadedAt: new Date().toISOString(),
    });
  }

  return NextResponse.json({ files: uploadedFiles });
}

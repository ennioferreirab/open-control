import { NextRequest, NextResponse } from "next/server";
import { ConvexHttpClient } from "convex/browser";
import { deleteSkillFromDisk, writeSkillToDisk } from "@/lib/skillDiskWriter";

type AdminConvexClient = ConvexHttpClient & {
  query(name: string, args: Record<string, unknown>): Promise<unknown>;
  mutation(name: string | unknown, args: Record<string, unknown>): Promise<unknown>;
  setAdminAuth(token: string): void;
};

function getClient(): AdminConvexClient {
  const client = new ConvexHttpClient(
    process.env.CONVEX_URL || process.env.NEXT_PUBLIC_CONVEX_URL!,
  ) as AdminConvexClient;
  client.setAdminAuth(process.env.CONVEX_ADMIN_KEY!);
  return client;
}

function parseSkillMetadata(raw: unknown): unknown {
  if (typeof raw !== "string") {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export async function GET(request: NextRequest) {
  try {
    const convex = getClient();

    const skills = (await convex.query("skills:list", {})) as Array<Record<string, unknown>>;

    const { searchParams } = new URL(request.url);
    const onlyAvailable = searchParams.get("available") === "true";

    const mapped = skills.map((skill) => ({
      name: skill.name,
      description: skill.description,
      source: skill.source,
      always: skill.always === true,
      available: skill.available === true,
      supportedProviders: Array.isArray(skill.supportedProviders)
        ? skill.supportedProviders.filter((value) => typeof value === "string")
        : [],
      requires: typeof skill.requires === "string" ? skill.requires : null,
      metadata: parseSkillMetadata(skill.metadata),
    }));

    const result = onlyAvailable ? mapped.filter((skill) => skill.available) : mapped;

    return NextResponse.json({ skills: result });
  } catch (error) {
    console.error("Failed to list skills:", error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Failed to list skills",
      },
      { status: 500 },
    );
  }
}

const VALID_PROVIDERS = ["claude-code", "codex", "nanobot"];
const VALID_SOURCES = ["builtin", "workspace"];

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, description, content, source, supportedProviders, ...optional } = body;

    if (!name || typeof name !== "string") {
      return NextResponse.json({ error: "name is required" }, { status: 400 });
    }

    if (!description || typeof description !== "string") {
      return NextResponse.json({ error: "description is required" }, { status: 400 });
    }

    if (!content || typeof content !== "string") {
      return NextResponse.json({ error: "content is required" }, { status: 400 });
    }

    const resolvedSource = source ?? "workspace";
    if (!VALID_SOURCES.includes(resolvedSource)) {
      return NextResponse.json(
        { error: `source must be one of: ${VALID_SOURCES.join(", ")}` },
        { status: 400 },
      );
    }

    const resolvedProviders: string[] = Array.isArray(supportedProviders)
      ? supportedProviders.filter(
          (p: unknown) => typeof p === "string" && VALID_PROVIDERS.includes(p),
        )
      : ["claude-code"];

    const resolvedMetadata =
      typeof optional.metadata === "string"
        ? optional.metadata
        : optional.metadata != null
          ? JSON.stringify(optional.metadata)
          : undefined;

    // Write SKILL.md to disk (before Convex — fail fast)
    writeSkillToDisk(name, description, content, {
      always: optional.always === true,
      metadata: resolvedMetadata,
    });

    const convex = getClient();

    await convex.mutation("skills:upsertByName", {
      name,
      description,
      content,
      source: resolvedSource,
      supportedProviders: resolvedProviders,
      available: optional.available !== false,
      metadata: resolvedMetadata,
      always: optional.always === true ? true : undefined,
      requires: typeof optional.requires === "string" ? optional.requires : undefined,
    });

    return NextResponse.json({ success: true, name });
  } catch (error) {
    console.error("Skill registration failed:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to register skill" },
      { status: 500 },
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const name = searchParams.get("name");

    if (!name) {
      return NextResponse.json({ error: "name query parameter is required" }, { status: 400 });
    }

    const convex = getClient();

    await convex.mutation("skills:deleteByName", { name });

    // Best-effort disk cleanup
    deleteSkillFromDisk(name);

    return NextResponse.json({ success: true, name });
  } catch (error) {
    console.error("Skill deletion failed:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to delete skill" },
      { status: 500 },
    );
  }
}

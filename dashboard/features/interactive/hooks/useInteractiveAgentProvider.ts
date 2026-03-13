import type { Doc } from "@/convex/_generated/dataModel";

export function getInteractiveAgentProvider(
  agent: Pick<Doc<"agents">, "model" | "claudeCodeOpts" | "interactiveProvider"> | null | undefined,
): string | null {
  if (agent?.interactiveProvider) {
    return agent.interactiveProvider;
  }
  const model = agent?.model ?? null;
  if (model?.startsWith("cc/")) {
    return "claude-code";
  }
  if (
    model?.startsWith("codex/") ||
    model?.startsWith("openai-codex/") ||
    model?.startsWith("github-copilot/")
  ) {
    return "codex";
  }
  if (agent?.claudeCodeOpts) {
    return "claude-code";
  }
  return null;
}

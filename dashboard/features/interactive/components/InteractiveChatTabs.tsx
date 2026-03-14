"use client";

import { ReactNode } from "react";

interface InteractiveChatTabsProps {
  agentName: string;
  interactiveProvider: string | null;
  chatView: ReactNode;
}

/**
 * Chat view for interactive agents.
 *
 * The legacy "TUI" tab (PTY/tmux remote terminal) has been removed as part of
 * Story 28.7. The provider CLI live-share surface is now the primary path and
 * is rendered directly in TaskDetailSheet via the "live" tab. This component
 * now acts as a simple passthrough that renders the chat view for both
 * interactive and non-interactive agents.
 *
 * @deprecated The tab-switching behaviour is retired. Callers can use this
 * component for API compatibility, but it no longer renders the TUI terminal.
 */
export function InteractiveChatTabs({ chatView, ...props }: InteractiveChatTabsProps) {
  // agentName and interactiveProvider are retained in props for API compatibility
  // but are no longer used to render a TUI tab (Story 28.7 — TUI tab retired).
  void props;
  return <>{chatView}</>;
}

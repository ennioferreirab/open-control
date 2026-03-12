"use client";

import { Doc } from "@/convex/_generated/dataModel";
import { useSidebar } from "@/components/ui/sidebar";
import { SidebarMenuItem, SidebarMenuButton } from "@/components/ui/sidebar";
import { useAgentSidebarItemState } from "@/features/agents/hooks/useAgentSidebarItemState";
import { RotateCcw, Trash2, Terminal } from "lucide-react";
import type { AgentStatus } from "@/lib/constants";
import { useBoard } from "@/components/BoardContext";

const STATUS_DOT_STYLES: Record<AgentStatus, string> = {
  active: "bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.5)]",
  idle: "bg-muted-foreground",
  crashed: "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]",
};

const DISABLED_DOT_STYLE = "bg-red-500";

const AVATAR_COLORS = [
  "bg-blue-500",
  "bg-emerald-500",
  "bg-violet-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-cyan-500",
  "bg-indigo-500",
  "bg-teal-500",
];

export function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export function getInitials(displayName: string): string {
  const words = displayName.trim().split(/\s+/);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return displayName.slice(0, 2).toUpperCase();
}

interface AgentSidebarItemProps {
  agent: Doc<"agents">;
  onClick?: () => void;
  onChat?: () => void;
  onDelete?: () => void;
  onRestore?: () => void;
}

export function AgentSidebarItem({ agent, onClick, onDelete, onRestore }: AgentSidebarItemProps) {
  const { state, isMobile } = useSidebar();
  const isCollapsed = state === "collapsed" && !isMobile;
  const initials = getInitials(agent.displayName);
  const avatarColor = getAvatarColor(agent.name);
  const isDisabled = agent.enabled === false;

  const isRemoteTerminal = agent.role === "remote-terminal";
  const { toggleTerminal, openTerminals } = useBoard();

  // Query for active terminal sessions only when this is a remote-terminal agent
  const { terminalSessions } = useAgentSidebarItemState(agent.name, isRemoteTerminal);

  const isSleeping = isRemoteTerminal && terminalSessions?.some((s) => s.sleepMode === true);

  const statusStyle = isDisabled
    ? DISABLED_DOT_STYLE
    : isSleeping
      ? "bg-blue-400"
      : (STATUS_DOT_STYLES[agent.status as AgentStatus] ?? STATUS_DOT_STYLES.idle);

  const ipAddress = agent.variables?.find((variable) => variable.name === "ipAddress")?.value;

  const handleClick = () => {
    if (isRemoteTerminal && terminalSessions && terminalSessions.length > 0) {
      const session = terminalSessions[0];
      toggleTerminal(session.sessionId, agent.name);
      return;
    }
    onClick?.();
  };

  const isTerminalOpen =
    isRemoteTerminal &&
    openTerminals.some((t) =>
      terminalSessions?.some(
        (sess) => sess.sessionId === t.sessionId && t.agentName === agent.name,
      ),
    );

  const tooltipContent = isDisabled
    ? `${agent.displayName} - ${agent.role} - Deactivated`
    : `${agent.displayName} - ${agent.role} - ${agent.status}`;

  if (isCollapsed) {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton
          size="lg"
          tooltip={tooltipContent}
          onClick={handleClick}
          className="!w-full !h-auto !p-2 flex items-center justify-center cursor-pointer"
        >
          <div className="relative">
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white ${avatarColor}`}
            >
              {isRemoteTerminal ? <Terminal className="h-4 w-4" /> : initials}
            </div>
            <span
              className={`absolute bottom-0 right-0 h-2 w-2 rounded-full ring-2 ring-sidebar transition-colors duration-200 ${statusStyle}`}
            />
          </div>
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  }

  const isDeletedItem = !!onRestore;

  return (
    <SidebarMenuItem className="flex items-center">
      <SidebarMenuButton
        size="lg"
        onClick={handleClick}
        className={`!h-auto flex-1 ${isDeletedItem ? "opacity-50 cursor-default" : "cursor-pointer"} ${isTerminalOpen ? "bg-accent" : ""}`}
      >
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white ${avatarColor}`}
        >
          {isRemoteTerminal ? <Terminal className="h-4 w-4" /> : initials}
        </div>
        <div
          className={`flex flex-1 flex-col overflow-hidden ${isDisabled ? "text-muted-foreground opacity-60" : ""}`}
        >
          {isRemoteTerminal ? (
            <>
              <span
                className={`truncate text-xs font-mono ${isDisabled ? "" : "text-sidebar-foreground/70"}`}
              >
                {ipAddress || agent.displayName}
              </span>
              <span
                className={`truncate text-xs ${isDisabled ? "" : "text-sidebar-foreground/50"}`}
              >
                {agent.displayName}
              </span>
            </>
          ) : (
            <>
              <span
                className={`truncate text-sm font-medium ${isDisabled ? "" : "text-sidebar-foreground"}`}
              >
                {agent.displayName}
              </span>
              <span
                className={`truncate text-xs ${isDisabled ? "" : "text-sidebar-foreground/70"}`}
              >
                {agent.role}
              </span>
            </>
          )}
        </div>
        {!onDelete && !onRestore && (
          <span
            className={`h-2 w-2 shrink-0 rounded-full transition-colors duration-200 ${statusStyle}`}
          />
        )}
      </SidebarMenuButton>
      {onDelete && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="shrink-0 px-2 text-muted-foreground hover:text-destructive transition-colors"
          aria-label={`Delete ${agent.displayName}`}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      )}
      {onRestore && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRestore();
          }}
          className="shrink-0 px-2 text-muted-foreground hover:text-foreground transition-colors"
          aria-label={`Restore ${agent.displayName}`}
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      )}
    </SidebarMenuItem>
  );
}

"use client";

import { Doc } from "@/convex/_generated/dataModel";
import { useSidebar } from "@/components/ui/sidebar";
import { SidebarMenuItem, SidebarMenuButton } from "@/components/ui/sidebar";
import { useAgentSidebarItemState } from "@/features/agents/hooks/useAgentSidebarItemState";
import { RotateCcw, Terminal } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import type { AgentStatus } from "@/lib/constants";
import { useBoard } from "@/components/BoardContext";
import { getInitials, getAvatarColor } from "@/lib/agentUtils";

const STATUS_DOT_STYLES: Record<AgentStatus, string> = {
  active: "bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.5)]",
  idle: "bg-muted-foreground",
  crashed: "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]",
};

const DISABLED_DOT_STYLE = "bg-red-500";

interface AgentSidebarItemProps {
  agent: Doc<"agents">;
  onClick?: () => void;
  onChat?: () => void;
  onRestore?: () => void;
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: () => void;
}

export function AgentSidebarItem({
  agent,
  onClick,
  onRestore,
  selectable,
  selected,
  onToggleSelect,
}: AgentSidebarItemProps) {
  const { state, isMobile } = useSidebar();
  const isCollapsed = state === "collapsed" && !isMobile;
  const initials = getInitials(agent.name);
  const avatarColor = getAvatarColor(agent.name);
  const isDisabled = agent.enabled === false;

  const isNanobot = agent.name === "nanobot";
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
    if (selectable) {
      onToggleSelect?.();
      return;
    }
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
    ? `${agent.name} - ${agent.role} - Deactivated`
    : `${agent.name} - ${agent.role} - ${agent.status}`;

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
            {isNanobot ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src="/bento.png"
                alt="Bento"
                className="h-8 w-8 shrink-0 rounded-full object-cover"
              />
            ) : (
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white ${avatarColor}`}
              >
                {isRemoteTerminal ? <Terminal className="h-4 w-4" /> : initials}
              </div>
            )}
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
        size="default"
        onClick={handleClick}
        className={`!h-8 flex-1 ${isDeletedItem ? "opacity-50 cursor-default" : "cursor-pointer"} ${isTerminalOpen ? "bg-accent" : ""}`}
      >
        {isNanobot ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src="/bento.png"
            alt="Bento"
            className="h-5 w-5 shrink-0 rounded-full object-cover"
          />
        ) : (
          <div
            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-medium text-white ${avatarColor}`}
          >
            {isRemoteTerminal ? <Terminal className="h-3 w-3" /> : initials}
          </div>
        )}
        <span
          className={`truncate text-xs ${isDisabled ? "text-muted-foreground opacity-60" : isRemoteTerminal ? "font-mono text-sidebar-foreground/70" : "text-sidebar-foreground"}`}
        >
          {isRemoteTerminal ? ipAddress || agent.name : agent.name}
        </span>
        {!selectable && !onRestore && (
          <span
            className={`h-1.5 w-1.5 shrink-0 rounded-full transition-colors duration-200 ${statusStyle}`}
          />
        )}
      </SidebarMenuButton>
      {selectable && (
        <div className="shrink-0 px-2">
          <Checkbox
            checked={selected}
            onCheckedChange={() => onToggleSelect?.()}
            aria-label={`Select ${agent.name}`}
          />
        </div>
      )}
      {onRestore && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRestore();
          }}
          className="shrink-0 px-2 text-muted-foreground hover:text-foreground transition-colors"
          aria-label={`Restore ${agent.name}`}
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      )}
    </SidebarMenuItem>
  );
}

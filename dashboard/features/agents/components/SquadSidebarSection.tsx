"use client";

import { Users } from "lucide-react";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from "@/components/ui/sidebar";
import { Checkbox } from "@/components/ui/checkbox";
import { useSquadSidebarData } from "@/features/agents/hooks/useSquadSidebarData";
import type { Id } from "@/convex/_generated/dataModel";

interface SquadSidebarSectionProps {
  onSelectSquad: (squadId: Id<"squadSpecs">) => void;
  deleteMode?: boolean;
  selectedSquadIds?: Set<string>;
  onToggleSquadSelect?: (squadId: Id<"squadSpecs">, displayName: string) => void;
}

function getSquadInitials(displayName: string): string {
  const words = displayName.trim().split(/\s+/);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return displayName.slice(0, 2).toUpperCase();
}

export function SquadSidebarSection({
  onSelectSquad,
  deleteMode,
  selectedSquadIds,
  onToggleSquadSelect,
}: SquadSidebarSectionProps) {
  const { squads, isLoading } = useSquadSidebarData();

  return (
    <SidebarGroup>
      <SidebarGroupLabel className="flex items-center gap-1">
        <Users className="h-3.5 w-3.5" />
        Squads
      </SidebarGroupLabel>
      {!isLoading && squads.length === 0 && (
        <p className="px-2 py-3 text-xs text-muted-foreground">
          No squads yet. Create one to get started.
        </p>
      )}
      <SidebarMenu>
        {squads.map((squad) => (
          <SidebarMenuItem key={squad._id} className="flex items-center">
            <SidebarMenuButton
              size="lg"
              onClick={() =>
                deleteMode
                  ? onToggleSquadSelect?.(squad._id, squad.displayName)
                  : onSelectSquad(squad._id)
              }
              className="!h-auto cursor-pointer"
              tooltip={`${squad.displayName}${squad.description ? ` — ${squad.description}` : ""}`}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet-500 text-xs font-medium text-white">
                {getSquadInitials(squad.displayName)}
              </div>
              <div className="flex flex-1 flex-col overflow-hidden">
                <span className="truncate text-sm font-medium text-sidebar-foreground">
                  {squad.displayName}
                </span>
                {squad.description && (
                  <span className="truncate text-xs text-sidebar-foreground/70">
                    {squad.description}
                  </span>
                )}
              </div>
            </SidebarMenuButton>
            {deleteMode && (
              <div className="shrink-0 px-2">
                <Checkbox
                  checked={selectedSquadIds?.has(squad._id)}
                  onCheckedChange={() => onToggleSquadSelect?.(squad._id, squad.displayName)}
                  aria-label={`Select ${squad.displayName}`}
                />
              </div>
            )}
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  );
}

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
import { getInitials } from "@/lib/agentUtils";
import type { Id } from "@/convex/_generated/dataModel";

interface SquadSidebarSectionProps {
  onSelectSquad: (squadId: Id<"squadSpecs">) => void;
  deleteMode?: boolean;
  selectedSquadIds?: Set<string>;
  onToggleSquadSelect?: (squadId: Id<"squadSpecs">, displayName: string | undefined) => void;
  filterQuery?: string;
}

export function SquadSidebarSection({
  onSelectSquad,
  deleteMode,
  selectedSquadIds,
  onToggleSquadSelect,
  filterQuery,
}: SquadSidebarSectionProps) {
  const { squads, isLoading } = useSquadSidebarData();

  const filteredSquads = filterQuery
    ? squads.filter((s) => {
        const lower = filterQuery.toLowerCase();
        return (
          (s.displayName ?? "").toLowerCase().includes(lower) ||
          s.name.toLowerCase().includes(lower)
        );
      })
    : squads;

  return (
    <SidebarGroup>
      <SidebarGroupLabel className="flex items-center gap-1">
        <Users className="h-3.5 w-3.5" />
        Squads
      </SidebarGroupLabel>
      {!isLoading && filteredSquads.length === 0 && (
        <p className="px-2 py-3 text-xs text-muted-foreground">
          No squads yet. Create one to get started.
        </p>
      )}
      <div className="overflow-y-auto max-h-[560px]">
        <SidebarMenu>
          {filteredSquads.map((squad) => (
            <SidebarMenuItem key={squad._id} className="flex items-center">
              <SidebarMenuButton
                size="default"
                onClick={() =>
                  deleteMode
                    ? onToggleSquadSelect?.(squad._id, squad.displayName)
                    : onSelectSquad(squad._id)
                }
                className="!h-8 cursor-pointer"
                tooltip={`${squad.name}${squad.description ? ` — ${squad.description}` : ""}`}
              >
                <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-500 text-[10px] font-medium text-white">
                  {getInitials(squad.name)}
                </div>
                <span className="truncate text-xs text-sidebar-foreground">{squad.name}</span>
              </SidebarMenuButton>
              {deleteMode && (
                <div className="shrink-0 px-2">
                  <Checkbox
                    checked={selectedSquadIds?.has(squad._id)}
                    onCheckedChange={() => onToggleSquadSelect?.(squad._id, squad.displayName)}
                    aria-label={`Select ${squad.name}`}
                  />
                </div>
              )}
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </div>
    </SidebarGroup>
  );
}

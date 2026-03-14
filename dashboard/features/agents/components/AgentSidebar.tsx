"use client";

import { useState, useCallback } from "react";
import { Bot, ChevronDown, Plus, RotateCcw, Shield, Terminal, Trash2, Users } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { AgentConfigSheet } from "@/features/agents/components/AgentConfigSheet";
import { AgentSidebarItem } from "@/features/agents/components/AgentSidebarItem";
import { CreateAuthoringDialog } from "@/features/agents/components/CreateAuthoringDialog";
import { AgentAuthoringWizard } from "@/features/agents/components/AgentAuthoringWizard";
import { SquadAuthoringWizard } from "@/features/agents/components/SquadAuthoringWizard";
import { SquadSidebarSection } from "@/features/agents/components/SquadSidebarSection";
import { SquadDetailSheet } from "@/features/agents/components/SquadDetailSheet";
import { useAgentSidebarData } from "@/features/agents/hooks/useAgentSidebarData";
import { useSquadSidebarData } from "@/features/agents/hooks/useSquadSidebarData";
import type { Id } from "@/convex/_generated/dataModel";

type SelectableItem =
  | { type: "agent"; name: string; displayName: string }
  | { type: "squad"; id: Id<"squadSpecs">; displayName: string };

export function AgentSidebar() {
  const {
    deletedAgents,
    isAgentsLoading,
    regularAgents,
    remoteAgents,
    restoreAgent,
    softDeleteAgent,
    systemAgents,
  } = useAgentSidebarData();
  const { archiveSquad, archivedSquads, unarchiveSquad } = useSquadSidebarData();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showCreateChooser, setShowCreateChooser] = useState(false);
  const [showAgentWizard, setShowAgentWizard] = useState(false);
  const [showSquadWizard, setShowSquadWizard] = useState(false);
  const [selectedSquadId, setSelectedSquadId] = useState<Id<"squadSpecs"> | null>(null);
  const [systemOpen, setSystemOpen] = useState(true);
  const [deletedOpen, setDeletedOpen] = useState(false);
  const [remoteOpen, setRemoteOpen] = useState(true);
  const [deleteMode, setDeleteMode] = useState(false);
  const [selectedItems, setSelectedItems] = useState<Map<string, SelectableItem>>(new Map());
  const [showBulkDeleteDialog, setShowBulkDeleteDialog] = useState(false);
  const [itemToRestore, setItemToRestore] = useState<
    | { type: "agent"; displayName: string; name: string }
    | { type: "squad"; displayName: string; id: Id<"squadSpecs"> }
    | null
  >(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  const toggleDeleteMode = useCallback(() => {
    setDeleteMode((current) => {
      if (current) setSelectedItems(new Map());
      return !current;
    });
  }, []);

  const toggleItemSelection = useCallback((key: string, item: SelectableItem) => {
    setSelectedItems((prev) => {
      const next = new Map(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.set(key, item);
      }
      return next;
    });
  }, []);

  const selectedSquadIds = new Set(
    Array.from(selectedItems.entries())
      .filter(([, item]) => item.type === "squad")
      .map(([key]) => key.replace("squad:", "")),
  );

  const handleBulkDelete = async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    try {
      const promises: Promise<void>[] = [];
      for (const item of selectedItems.values()) {
        if (item.type === "agent") {
          promises.push(softDeleteAgent(item.name));
        } else {
          promises.push(archiveSquad(item.id));
        }
      }
      await Promise.all(promises);
      setShowBulkDeleteDialog(false);
      setSelectedItems(new Map());
      setDeleteMode(false);
    } catch {
      // Keep dialog open so user can retry.
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <Sidebar collapsible="icon">
        <SidebarHeader className="border-b border-sidebar-border p-0">
          <div className="flex h-[60px] items-center gap-2 px-4 group-data-[collapsible=icon]:px-0">
            <Bot className="h-5 w-5 shrink-0 text-sidebar-foreground/70 group-data-[collapsible=icon]:hidden" />
            <span className="truncate text-sm font-semibold text-sidebar-foreground group-data-[collapsible=icon]:hidden">
              Agents
            </span>
            <div className="ml-auto flex items-center gap-1 group-data-[collapsible=icon]:hidden">
              <button
                onClick={toggleDeleteMode}
                className={`p-1 rounded transition-colors ${deleteMode ? "text-destructive" : "text-muted-foreground hover:text-destructive"}`}
                aria-label={deleteMode ? "Exit delete mode" : "Delete agents or squads"}
                aria-pressed={deleteMode}
              >
                <Trash2 className="h-4 w-4" />
              </button>
              <SidebarTrigger />
            </div>
            <div className="hidden group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:w-full group-data-[collapsible=icon]:justify-center">
              <SidebarTrigger />
            </div>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SquadSidebarSection
            onSelectSquad={(id) => setSelectedSquadId(id)}
            deleteMode={deleteMode}
            selectedSquadIds={selectedSquadIds}
            onToggleSquadSelect={(squadId, displayName) =>
              toggleItemSelection(`squad:${squadId}`, {
                type: "squad",
                id: squadId,
                displayName,
              })
            }
          />

          <SidebarGroup>
            <SidebarGroupLabel>Registered</SidebarGroupLabel>
            {!isAgentsLoading && regularAgents.length === 0 && (
              <p className="px-2 py-4 text-xs text-muted-foreground">
                No agents found. Add a YAML config to{" "}
                <code className="rounded bg-muted px-1 py-0.5 text-[11px]">~/.nanobot/agents/</code>
              </p>
            )}
            <SidebarMenu>
              {regularAgents.map((agent) => (
                <AgentSidebarItem
                  key={agent._id}
                  agent={agent}
                  onClick={() => setSelectedAgent(agent.name)}
                  selectable={deleteMode}
                  selected={selectedItems.has(`agent:${agent.name}`)}
                  onToggleSelect={() =>
                    toggleItemSelection(`agent:${agent.name}`, {
                      type: "agent",
                      name: agent.name,
                      displayName: agent.displayName,
                    })
                  }
                />
              ))}
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="lg"
                  tooltip="Create Agent or Squad"
                  onClick={() => setShowCreateChooser(true)}
                  className="!h-auto cursor-pointer"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-dashed border-muted-foreground/40">
                    <Plus className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <span className="text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
                    Create
                  </span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroup>

          {systemAgents.length > 0 && (
            <SidebarGroup>
              <Collapsible open={systemOpen} onOpenChange={setSystemOpen}>
                <CollapsibleTrigger asChild>
                  <SidebarGroupLabel className="cursor-pointer hover:text-sidebar-foreground/80">
                    <Shield className="mr-1 h-3 w-3" />
                    System
                    <ChevronDown
                      className={`ml-auto h-3 w-3 transition-transform ${systemOpen ? "" : "-rotate-90"}`}
                    />
                  </SidebarGroupLabel>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenu>
                    {systemAgents.map((agent) => (
                      <AgentSidebarItem
                        key={agent._id}
                        agent={agent}
                        onClick={() => setSelectedAgent(agent.name)}
                      />
                    ))}
                  </SidebarMenu>
                </CollapsibleContent>
              </Collapsible>
            </SidebarGroup>
          )}

          {remoteAgents.length > 0 && (
            <SidebarGroup>
              <Collapsible open={remoteOpen} onOpenChange={setRemoteOpen}>
                <CollapsibleTrigger asChild>
                  <SidebarGroupLabel className="cursor-pointer hover:text-sidebar-foreground/80">
                    <Terminal className="mr-1 h-3 w-3" />
                    Remoto
                    <ChevronDown
                      className={`ml-auto h-3 w-3 transition-transform ${remoteOpen ? "" : "-rotate-90"}`}
                    />
                  </SidebarGroupLabel>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenu>
                    {remoteAgents.map((agent) => (
                      <AgentSidebarItem
                        key={agent._id}
                        agent={agent}
                        onClick={() => setSelectedAgent(agent.name)}
                        selectable={deleteMode}
                        selected={selectedItems.has(`agent:${agent.name}`)}
                        onToggleSelect={() =>
                          toggleItemSelection(`agent:${agent.name}`, {
                            type: "agent",
                            name: agent.name,
                            displayName: agent.displayName,
                          })
                        }
                      />
                    ))}
                  </SidebarMenu>
                </CollapsibleContent>
              </Collapsible>
            </SidebarGroup>
          )}

          {((deletedAgents && deletedAgents.length > 0) || archivedSquads.length > 0) && (
            <SidebarGroup>
              <Collapsible open={deletedOpen} onOpenChange={setDeletedOpen}>
                <CollapsibleTrigger asChild>
                  <SidebarGroupLabel className="cursor-pointer hover:text-sidebar-foreground/80">
                    <Trash2 className="mr-1 h-3 w-3" />
                    Deleted
                    <ChevronDown
                      className={`ml-auto h-3 w-3 transition-transform ${deletedOpen ? "" : "-rotate-90"}`}
                    />
                  </SidebarGroupLabel>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenu>
                    {deletedAgents?.map((agent) => (
                      <AgentSidebarItem
                        key={agent._id}
                        agent={agent}
                        onRestore={() =>
                          setItemToRestore({
                            type: "agent",
                            displayName: agent.displayName,
                            name: agent.name,
                          })
                        }
                      />
                    ))}
                    {archivedSquads.map((squad) => (
                      <SidebarMenuItem key={squad._id} className="flex items-center">
                        <SidebarMenuButton
                          size="lg"
                          className="!h-auto flex-1 opacity-50 cursor-default"
                        >
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet-500/50 text-xs font-medium text-white">
                            <Users className="h-4 w-4" />
                          </div>
                          <div className="flex flex-1 flex-col overflow-hidden">
                            <span className="truncate text-sm font-medium text-sidebar-foreground">
                              {squad.displayName}
                            </span>
                            <span className="truncate text-xs text-sidebar-foreground/70">
                              squad
                            </span>
                          </div>
                        </SidebarMenuButton>
                        <button
                          onClick={() =>
                            setItemToRestore({
                              type: "squad",
                              displayName: squad.displayName,
                              id: squad._id,
                            })
                          }
                          className="shrink-0 px-2 text-muted-foreground hover:text-foreground transition-colors"
                          aria-label={`Restore ${squad.displayName}`}
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                        </button>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </CollapsibleContent>
              </Collapsible>
            </SidebarGroup>
          )}
        </SidebarContent>
        {deleteMode && selectedItems.size > 0 && (
          <SidebarFooter className="border-t border-sidebar-border p-3 group-data-[collapsible=icon]:hidden">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">{selectedItems.size} selected</span>
              <Button variant="destructive" size="sm" onClick={() => setShowBulkDeleteDialog(true)}>
                Delete selected
              </Button>
            </div>
          </SidebarFooter>
        )}
      </Sidebar>
      <AgentConfigSheet agentName={selectedAgent} onClose={() => setSelectedAgent(null)} />
      <CreateAuthoringDialog
        open={showCreateChooser}
        onClose={() => setShowCreateChooser(false)}
        onSelectAgent={() => setShowAgentWizard(true)}
        onSelectSquad={() => setShowSquadWizard(true)}
      />
      <AgentAuthoringWizard open={showAgentWizard} onClose={() => setShowAgentWizard(false)} />
      <SquadAuthoringWizard open={showSquadWizard} onClose={() => setShowSquadWizard(false)} />
      <SquadDetailSheet squadId={selectedSquadId} onClose={() => setSelectedSquadId(null)} />
      <AlertDialog
        open={showBulkDeleteDialog}
        onOpenChange={(open) => {
          if (!open) setShowBulkDeleteDialog(false);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selectedItems.size} item{selectedItems.size > 1 ? "s" : ""}?
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div>
                <p className="mb-2">Are you sure you want to delete the following?</p>
                <ul className="list-disc pl-5 space-y-1">
                  {Array.from(selectedItems.values()).map((item) => (
                    <li key={item.type === "agent" ? `agent:${item.name}` : `squad:${item.id}`}>
                      <strong>{item.displayName}</strong>{" "}
                      <span className="text-muted-foreground">({item.type})</span>
                    </li>
                  ))}
                </ul>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isDeleting}
              onClick={handleBulkDelete}
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog open={!!itemToRestore} onOpenChange={(open) => !open && setItemToRestore(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Restore {itemToRestore?.type === "squad" ? "squad" : "agent"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Restore <strong>{itemToRestore?.displayName}</strong>?{" "}
              {itemToRestore?.type === "squad"
                ? "The squad will return to the squads list."
                : "The agent will return to the registered list and its local files will be recreated on the next sync."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={isRestoring}
              onClick={async () => {
                if (itemToRestore && !isRestoring) {
                  setIsRestoring(true);
                  try {
                    if (itemToRestore.type === "agent") {
                      await restoreAgent(itemToRestore.name);
                    } else {
                      await unarchiveSquad(itemToRestore.id);
                    }
                    setItemToRestore(null);
                  } catch {
                    // Keep dialog open so user can retry.
                  } finally {
                    setIsRestoring(false);
                  }
                }
              }}
            >
              {isRestoring ? "Restoring..." : "Restore"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

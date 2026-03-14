"use client";

import { useState } from "react";
import { Bot, ChevronDown, Plus, Shield, Terminal, Trash2 } from "lucide-react";
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
import {
  Sidebar,
  SidebarContent,
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
import type { Id } from "@/convex/_generated/dataModel";

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
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showCreateChooser, setShowCreateChooser] = useState(false);
  const [showAgentWizard, setShowAgentWizard] = useState(false);
  const [showSquadWizard, setShowSquadWizard] = useState(false);
  const [selectedSquadId, setSelectedSquadId] = useState<Id<"squadSpecs"> | null>(null);
  const [systemOpen, setSystemOpen] = useState(true);
  const [deletedOpen, setDeletedOpen] = useState(false);
  const [remoteOpen, setRemoteOpen] = useState(true);
  const [deleteMode, setDeleteMode] = useState(false);
  const [agentToDelete, setAgentToDelete] = useState<{ displayName: string; name: string } | null>(
    null,
  );
  const [agentToRestore, setAgentToRestore] = useState<{
    displayName: string;
    name: string;
  } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  return (
    <>
      <Sidebar collapsible="icon">
        <SidebarHeader className="border-b border-sidebar-border p-0">
          <div className="flex h-[60px] items-center gap-2 px-4 group-data-[collapsible=icon]:px-0">
            <Bot className="h-5 w-5 shrink-0 text-sidebar-foreground/70 group-data-[collapsible=icon]:hidden" />
            <span className="truncate text-sm font-semibold text-sidebar-foreground group-data-[collapsible=icon]:hidden">
              Agents
            </span>
            <div className="ml-auto group-data-[collapsible=icon]:hidden">
              <SidebarTrigger />
            </div>
            <div className="hidden group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:w-full group-data-[collapsible=icon]:justify-center">
              <SidebarTrigger />
            </div>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SquadSidebarSection onSelectSquad={(id) => setSelectedSquadId(id)} />

          <SidebarGroup>
            <SidebarGroupLabel className="flex items-center">
              Registered
              <button
                onClick={() => setDeleteMode((current) => !current)}
                className={`ml-auto transition-colors ${deleteMode ? "text-destructive" : "text-muted-foreground hover:text-destructive"}`}
                aria-label={deleteMode ? "Exit delete mode" : "Delete an agent"}
                aria-pressed={deleteMode}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </SidebarGroupLabel>
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
                  onDelete={
                    deleteMode
                      ? () => setAgentToDelete({ displayName: agent.displayName, name: agent.name })
                      : undefined
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
                        onDelete={
                          deleteMode
                            ? () =>
                                setAgentToDelete({
                                  displayName: agent.displayName,
                                  name: agent.name,
                                })
                            : undefined
                        }
                      />
                    ))}
                  </SidebarMenu>
                </CollapsibleContent>
              </Collapsible>
            </SidebarGroup>
          )}

          {deletedAgents && deletedAgents.length > 0 && (
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
                    {deletedAgents.map((agent) => (
                      <AgentSidebarItem
                        key={agent._id}
                        agent={agent}
                        onRestore={() =>
                          setAgentToRestore({ displayName: agent.displayName, name: agent.name })
                        }
                      />
                    ))}
                  </SidebarMenu>
                </CollapsibleContent>
              </Collapsible>
            </SidebarGroup>
          )}
        </SidebarContent>
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
        open={!!agentToDelete}
        onOpenChange={(open) => {
          if (!open) {
            setAgentToDelete(null);
            setDeleteMode(false);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete agent?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{agentToDelete?.displayName}</strong>? This
              will remove it from the dashboard. The agent will re-appear if it reconnects.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isDeleting}
              onClick={async () => {
                if (agentToDelete && !isDeleting) {
                  setIsDeleting(true);
                  try {
                    await softDeleteAgent(agentToDelete.name);
                    setAgentToDelete(null);
                    setDeleteMode(false);
                  } catch {
                    // Keep dialog open so user can retry.
                  } finally {
                    setIsDeleting(false);
                  }
                }
              }}
            >
              {isDeleting ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog
        open={!!agentToRestore}
        onOpenChange={(open) => !open && setAgentToRestore(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Restore agent?</AlertDialogTitle>
            <AlertDialogDescription>
              Restore <strong>{agentToRestore?.displayName}</strong>? The agent will return to the
              registered list and its local files will be recreated on the next sync.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={isRestoring}
              onClick={async () => {
                if (agentToRestore && !isRestoring) {
                  setIsRestoring(true);
                  try {
                    await restoreAgent(agentToRestore.name);
                    setAgentToRestore(null);
                  } catch {
                    // Keep dialog open so user can retry.
                  } finally {
                    setIsRestoring(false);
                  }
                }
              }}
            >
              {isRestoring ? "Restoring…" : "Restore"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

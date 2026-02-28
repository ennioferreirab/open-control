"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Bot, Plus, Shield, ChevronDown, Trash2, Terminal } from "lucide-react";
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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { AgentSidebarItem } from "@/components/AgentSidebarItem";
import { AgentConfigSheet } from "@/components/AgentConfigSheet";
import { CreateAgentSheet } from "@/components/CreateAgentSheet";
import { SYSTEM_AGENT_NAMES } from "@/lib/constants";

export function AgentSidebar() {
  const agents = useQuery(api.agents.list);
  const deletedAgents = useQuery(api.agents.listDeleted);
  const softDeleteAgent = useMutation(api.agents.softDeleteAgent);
  const restoreAgent = useMutation(api.agents.restoreAgent);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showCreateSheet, setShowCreateSheet] = useState(false);
  const [systemOpen, setSystemOpen] = useState(true);
  const [deletedOpen, setDeletedOpen] = useState(false);
  const [deleteMode, setDeleteMode] = useState(false);
  const [agentToDelete, setAgentToDelete] = useState<{ name: string; displayName: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [agentToRestore, setAgentToRestore] = useState<{ name: string; displayName: string } | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);

  const [remoteOpen, setRemoteOpen] = useState(true);

  const { regularAgents, systemAgents, remoteAgents } = useMemo(() => {
    if (!agents) return { regularAgents: [], systemAgents: [], remoteAgents: [] };
    return {
      regularAgents: agents.filter((a) => !a.isSystem && !SYSTEM_AGENT_NAMES.has(a.name) && a.name !== "low-agent" && a.role !== "remote-terminal"),
      systemAgents: agents.filter((a) => (a.isSystem || SYSTEM_AGENT_NAMES.has(a.name)) && a.name !== "low-agent"),
      remoteAgents: agents.filter((a) => a.role === "remote-terminal"),
    };
  }, [agents]);

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
        {/* Registered agents */}
        <SidebarGroup>
          <SidebarGroupLabel className="flex items-center">
            Registered
            <button
              onClick={() => setDeleteMode((prev) => !prev)}
              className={`ml-auto transition-colors ${deleteMode ? "text-destructive" : "text-muted-foreground hover:text-destructive"}`}
              aria-label={deleteMode ? "Exit delete mode" : "Delete an agent"}
              aria-pressed={deleteMode}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </SidebarGroupLabel>
          {agents === undefined ? null : regularAgents.length === 0 ? (
            <p className="px-2 py-4 text-xs text-muted-foreground">
              No agents found. Add a YAML config to{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-[11px]">
                ~/.nanobot/agents/
              </code>
            </p>
          ) : null}
          <SidebarMenu>
            {agents !== undefined && regularAgents.map((agent) => (
              <AgentSidebarItem
                key={agent._id}
                agent={agent}
                onClick={() => setSelectedAgent(agent.name)}
                onDelete={deleteMode ? () => setAgentToDelete({ name: agent.name, displayName: agent.displayName }) : undefined}
              />
            ))}
            <SidebarMenuItem>
              <SidebarMenuButton
                size="lg"
                tooltip="Create Agent"
                onClick={() => setShowCreateSheet(true)}
                className="!h-auto cursor-pointer group-data-[collapsible=icon]:!w-full group-data-[collapsible=icon]:!p-2 group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:justify-center"
              >
                <div className="relative">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-dashed border-muted-foreground/40 group-data-[collapsible=icon]:h-8 group-data-[collapsible=icon]:w-8">
                    <Plus className="h-4 w-4 text-muted-foreground" />
                  </div>
                </div>
                <span className="text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
                  Create Agent
                </span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>

        {/* System agents */}
        {systemAgents.length > 0 && (
          <SidebarGroup>
            <Collapsible open={systemOpen} onOpenChange={setSystemOpen}>
              <CollapsibleTrigger asChild>
                <SidebarGroupLabel className="cursor-pointer hover:text-sidebar-foreground/80">
                  <Shield className="mr-1 h-3 w-3" />
                  System
                  <ChevronDown className={`ml-auto h-3 w-3 transition-transform ${systemOpen ? "" : "-rotate-90"}`} />
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

        {/* Remote terminal agents */}
        {remoteAgents.length > 0 && (
          <SidebarGroup>
            <Collapsible open={remoteOpen} onOpenChange={setRemoteOpen}>
              <CollapsibleTrigger asChild>
                <SidebarGroupLabel className="cursor-pointer hover:text-sidebar-foreground/80">
                  <Terminal className="mr-1 h-3 w-3" />
                  Remoto
                  <ChevronDown className={`ml-auto h-3 w-3 transition-transform ${remoteOpen ? "" : "-rotate-90"}`} />
                </SidebarGroupLabel>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <SidebarMenu>
                  {remoteAgents.map((agent) => (
                    <AgentSidebarItem
                      key={agent._id}
                      agent={agent}
                      onClick={() => setSelectedAgent(agent.name)}
                      onDelete={deleteMode ? () => setAgentToDelete({ name: agent.name, displayName: agent.displayName }) : undefined}
                    />
                  ))}
                </SidebarMenu>
              </CollapsibleContent>
            </Collapsible>
          </SidebarGroup>
        )}

        {/* Deleted agents */}
        {deletedAgents && deletedAgents.length > 0 && (
          <SidebarGroup>
            <Collapsible open={deletedOpen} onOpenChange={setDeletedOpen}>
              <CollapsibleTrigger asChild>
                <SidebarGroupLabel className="cursor-pointer hover:text-sidebar-foreground/80">
                  <Trash2 className="mr-1 h-3 w-3" />
                  Deleted
                  <ChevronDown className={`ml-auto h-3 w-3 transition-transform ${deletedOpen ? "" : "-rotate-90"}`} />
                </SidebarGroupLabel>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <SidebarMenu>
                  {deletedAgents.map((agent) => (
                    <AgentSidebarItem
                      key={agent._id}
                      agent={agent}
                      onRestore={() => setAgentToRestore({ name: agent.name, displayName: agent.displayName })}
                    />
                  ))}
                </SidebarMenu>
              </CollapsibleContent>
            </Collapsible>
          </SidebarGroup>
        )}
      </SidebarContent>
    </Sidebar>
    <AgentConfigSheet
      agentName={selectedAgent}
      onClose={() => setSelectedAgent(null)}
    />
    <CreateAgentSheet
      open={showCreateSheet}
      onClose={() => setShowCreateSheet(false)}
    />
    <AlertDialog open={!!agentToDelete} onOpenChange={(open) => { if (!open) { setAgentToDelete(null); setDeleteMode(false); } }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete agent?</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete <strong>{agentToDelete?.displayName}</strong>? This will remove it from the dashboard. The agent will re-appear if it reconnects.
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
                  await softDeleteAgent({ agentName: agentToDelete.name });
                  setAgentToDelete(null);
                  setDeleteMode(false);
                } catch {
                  // Keep dialog open so user can retry
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
    <AlertDialog open={!!agentToRestore} onOpenChange={(open) => { if (!open) setAgentToRestore(null); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Restore agent?</AlertDialogTitle>
          <AlertDialogDescription>
            Restore <strong>{agentToRestore?.displayName}</strong>? The agent will return to the registered list and its local files will be recreated on the next sync.
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
                  await restoreAgent({ agentName: agentToRestore.name });
                  setAgentToRestore(null);
                } catch {
                  // Keep dialog open so user can retry
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

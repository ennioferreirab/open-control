"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";
import { Bot, Plus, Shield, ChevronDown, Trash2 } from "lucide-react";
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
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
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
  const softDeleteAgent = useMutation(api.agents.softDeleteAgent);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showCreateSheet, setShowCreateSheet] = useState(false);
  const [systemOpen, setSystemOpen] = useState(true);
  const [deleteMode, setDeleteMode] = useState(false);
  const [agentToDelete, setAgentToDelete] = useState<{ name: string; displayName: string } | null>(null);

  const { regularAgents, systemAgents } = useMemo(() => {
    if (!agents) return { regularAgents: [], systemAgents: [] };
    return {
      regularAgents: agents.filter((a) => !a.isSystem && !SYSTEM_AGENT_NAMES.has(a.name)),
      systemAgents: agents.filter((a) => a.isSystem || SYSTEM_AGENT_NAMES.has(a.name)),
    };
  }, [agents]);

  return (
    <>
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-1">
          <Bot className="h-5 w-5 shrink-0 text-sidebar-foreground/70" />
          <span className="truncate text-sm font-semibold text-sidebar-foreground">
            Agents
          </span>
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
              title={deleteMode ? "Exit delete mode" : "Delete an agent"}
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
          ) : (
            <SidebarMenu>
              {regularAgents.map((agent) => (
                <AgentSidebarItem
                  key={agent._id}
                  agent={agent}
                  onClick={() => setSelectedAgent(agent.name)}
                  onDelete={deleteMode ? () => setAgentToDelete({ name: agent.name, displayName: agent.displayName }) : undefined}
                />
              ))}
            </SidebarMenu>
          )}
          <div className="px-2 pt-2">
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start gap-2 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setShowCreateSheet(true)}
            >
              <Plus className="h-3.5 w-3.5" />
              Create Agent
            </Button>
          </div>
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
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border">
        <SidebarTrigger />
      </SidebarFooter>
    </Sidebar>
    <AgentConfigSheet
      agentName={selectedAgent}
      onClose={() => setSelectedAgent(null)}
    />
    <CreateAgentSheet
      open={showCreateSheet}
      onClose={() => setShowCreateSheet(false)}
    />
    <AlertDialog open={!!agentToDelete} onOpenChange={(open) => !open && setAgentToDelete(null)}>
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
            onClick={async () => {
              if (agentToDelete) {
                await softDeleteAgent({ agentName: agentToDelete.name });
                setAgentToDelete(null);
                setDeleteMode(false);
              }
            }}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  );
}

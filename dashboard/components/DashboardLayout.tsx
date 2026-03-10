"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation } from "convex/react";
import { Id } from "../convex/_generated/dataModel";
import { api } from "../convex/_generated/api";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { AgentSidebar } from "@/components/AgentSidebar";
import { ActivityFeedPanel } from "@/components/ActivityFeedPanel";
import { TaskInput } from "@/components/TaskInput";
import { KanbanBoard } from "@/components/KanbanBoard";
import { TerminalBoard } from "@/components/TerminalBoard";
import { TaskDetailSheet } from "@/components/TaskDetailSheet";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { SettingsPanel } from "@/components/SettingsPanel";
import { TagsPanel } from "@/components/TagsPanel";
import { Settings, Tag, Clock, PanelRightOpen } from "lucide-react";
import { BoardProvider, useBoard } from "@/components/BoardContext";
import { BoardSelector } from "@/components/BoardSelector";
import { BoardSettingsSheet } from "@/components/BoardSettingsSheet";
import { CronJobsModal } from "@/components/CronJobsModal";
import { SearchBar } from "@/components/SearchBar";
import { parseSearch } from "@/lib/searchParser";
import {
  useGatewaySleepRuntime,
  useGatewaySleepCountdown,
} from "@/hooks/useGatewaySleepRuntime";

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    setMatches(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

function DashboardContent({ isXl }: { isXl: boolean }) {
  const [selectedTaskId, setSelectedTaskId] = useState<Id<"tasks"> | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [boardSettingsOpen, setBoardSettingsOpen] = useState(false);
  const [cronOpen, setCronOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activityPanelCollapsed, setActivityPanelCollapsed] = useState(true);

  const parsedSearch = useMemo(() => parseSearch(searchQuery), [searchQuery]);
  const { openTerminals, closeAllTerminals } = useBoard();
  const gatewaySleepRuntime = useGatewaySleepRuntime();
  const gatewaySleepCountdown = useGatewaySleepCountdown(gatewaySleepRuntime);
  const requestGatewaySleepMode = useMutation(api.settings.requestGatewaySleepMode);
  const gatewaySleepLabel =
    gatewaySleepRuntime == null
      ? "Gateway unavailable"
      : gatewaySleepRuntime.mode === "sleep"
        ? `Gateway sleeping · ${gatewaySleepCountdown ? `sync in ${gatewaySleepCountdown}` : `${gatewaySleepRuntime.pollIntervalSeconds}s`}`
        : `Gateway active · ${gatewaySleepCountdown ? `sleep in ${gatewaySleepCountdown}` : `${gatewaySleepRuntime.pollIntervalSeconds}s`}`;
  const gatewaySleepClasses =
    gatewaySleepRuntime?.mode === "sleep"
      ? "border-sky-200 bg-sky-50 text-sky-700"
      : gatewaySleepRuntime?.mode === "active"
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-border bg-muted text-muted-foreground";
  const gatewaySleepButtonLabel =
    gatewaySleepRuntime?.mode === "sleep" ? "Wake now" : "Sleep now";
  const gatewaySleepNextMode =
    gatewaySleepRuntime?.mode === "sleep" ? "active" : "sleep";

  return (
    <SidebarProvider defaultOpen={isXl} className="h-screen overflow-hidden">
      <AgentSidebar />
      <SidebarInset className="h-screen min-w-0 overflow-hidden">
        <div className="flex h-screen flex-col overflow-hidden bg-background">
          <header className="flex h-[60px] items-center justify-between border-b border-border px-4">
            <div className="flex items-center gap-1.5 md:gap-3 shrink-0">
              <SidebarTrigger className="md:hidden" />
              <h1
                className={`text-base md:text-xl font-bold text-foreground whitespace-nowrap${openTerminals.length > 0 ? " cursor-pointer hover:text-muted-foreground transition-colors" : ""}`}
                onClick={openTerminals.length > 0 ? closeAllTerminals : undefined}
              >
                <span className="md:hidden">M</span>
                <span className="hidden md:inline">Mission Control</span>
              </h1>
            </div>
            <div className="flex items-center gap-2 md:gap-3 flex-1 justify-center px-2 md:px-4 max-w-2xl">
              <BoardSelector onOpenSettings={() => setBoardSettingsOpen(true)} />
              <SearchBar onSearchChange={setSearchQuery} />
            </div>
            <div className="flex items-center gap-2 shrink-0 ml-auto">
              <div className="hidden items-center gap-2 md:flex">
                <span
                  className={`rounded-full border px-2 py-1 text-[11px] font-medium ${gatewaySleepClasses}`}
                >
                  {gatewaySleepLabel}
                </span>
                {gatewaySleepRuntime && (
                  <button
                    type="button"
                    onClick={() => {
                      void requestGatewaySleepMode({ mode: gatewaySleepNextMode });
                    }}
                    className="rounded-full border border-border px-2 py-1 text-[11px] font-medium text-foreground transition-colors hover:bg-accent"
                  >
                    {gatewaySleepButtonLabel}
                  </button>
                )}
              </div>
              <button
                aria-label="Open cron jobs"
                onClick={() => setCronOpen(true)}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <Clock className="h-4 w-4" />
              </button>
              <button
                aria-label="Open tags"
                onClick={() => setTagsOpen(true)}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <Tag className="h-4 w-4" />
              </button>
              <button
                aria-label="Open settings"
                onClick={() => setSettingsOpen(true)}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <Settings className="h-4 w-4" />
              </button>
              {activityPanelCollapsed && (
                <button
                  aria-label="Show activity feed"
                  onClick={() => setActivityPanelCollapsed(false)}
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  <PanelRightOpen className="h-4 w-4" />
                </button>
              )}
            </div>
          </header>

          <div className="border-b border-border px-4 py-3">
            <TaskInput />
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-4">
            {openTerminals.length > 0 ? (
              <TerminalBoard />
            ) : (
              <KanbanBoard
                onTaskClick={(taskId) => setSelectedTaskId(taskId)}
                search={parsedSearch}
              />
            )}
          </div>
        </div>
      </SidebarInset>
      <ActivityFeedPanel collapsed={activityPanelCollapsed} onCollapse={() => setActivityPanelCollapsed(true)} />
      <TaskDetailSheet
        taskId={selectedTaskId}
        onClose={() => setSelectedTaskId(null)}
      />
      <Sheet open={settingsOpen} onOpenChange={setSettingsOpen}>
        <SheetContent side="right" className="w-full sm:w-[600px] p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Settings</SheetTitle>
            <SheetDescription>Configure global system defaults</SheetDescription>
          </SheetHeader>
          <SettingsPanel />
        </SheetContent>
      </Sheet>
      <Sheet open={tagsOpen} onOpenChange={setTagsOpen}>
        <SheetContent side="right" className="w-full sm:w-[400px] p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Tags</SheetTitle>
            <SheetDescription>Manage predefined task tags</SheetDescription>
          </SheetHeader>
          <TagsPanel />
        </SheetContent>
      </Sheet>
      <BoardSettingsSheet
        open={boardSettingsOpen}
        onClose={() => setBoardSettingsOpen(false)}
      />
      <CronJobsModal
        open={cronOpen}
        onClose={() => setCronOpen(false)}
        onTaskClick={(taskId) => { setCronOpen(false); setSelectedTaskId(taskId as Id<"tasks">); }}
      />
    </SidebarProvider>
  );
}

export function DashboardLayout() {
  const isXl = useMediaQuery("(min-width: 1280px)");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Prevent flash of wrong layout during hydration
  if (!mounted) {
    return null;
  }

  return (
    <BoardProvider>
      <DashboardContent isXl={isXl} />
    </BoardProvider>
  );
}

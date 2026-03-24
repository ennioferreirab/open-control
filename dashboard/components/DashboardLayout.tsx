"use client";

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Id } from "@/convex/_generated/dataModel";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AgentSidebar } from "@/features/agents/components/AgentSidebar";
import { AgentConfigSheet } from "@/features/agents/components/AgentConfigSheet";
import { SquadDetailSheet } from "@/features/agents/components/SquadDetailSheet";
import { ActivityFeedPanel } from "@/features/activity/components/ActivityFeedPanel";
import { TaskInput } from "@/features/tasks/components/TaskInput";
import { KanbanBoard } from "@/features/boards/components/KanbanBoard";
import { TerminalBoard } from "@/features/terminal/components/TerminalBoard";
import { TaskDetailSheet } from "@/features/tasks/components/TaskDetailSheet";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { SettingsPanel } from "@/features/settings/components/SettingsPanel";
import { TagsPanel } from "@/features/settings/components/TagsPanel";
import { Settings, Tag, Clock, PanelRightOpen, Search } from "lucide-react";
import { BoardProvider, useBoard } from "@/components/BoardContext";
import { BoardSelector } from "@/features/boards/components/BoardSelector";
import { BoardSettingsSheet } from "@/features/boards/components/BoardSettingsSheet";
import { CronJobsModal } from "@/components/CronJobsModal";
import { SearchBar } from "@/features/search/components/SearchBar";
import { parseSearch } from "@/lib/searchParser";
import { useGatewaySleepRuntime, useGatewaySleepCountdown } from "@/hooks/useGatewaySleepRuntime";
import { useGatewaySleepModeRequest } from "@/features/settings/hooks/useGatewaySleepModeRequest";
import { CommandPalette } from "@/components/CommandPalette";
import type { CommandPaletteAction } from "@/hooks/useCommandPaletteSearch";
import { MobileTabBar } from "@/components/MobileTabBar";

function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onStoreChange: () => void) => {
      const mediaQueryList = window.matchMedia(query);
      mediaQueryList.addEventListener("change", onStoreChange);
      return () => mediaQueryList.removeEventListener("change", onStoreChange);
    },
    [query],
  );

  const getSnapshot = useCallback(() => window.matchMedia(query).matches, [query]);

  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

function useHydrated(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

function DashboardContent({ isXl }: { isXl: boolean }) {
  const [selectedTaskId, setSelectedTaskId] = useState<Id<"tasks"> | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedSquadId, setSelectedSquadId] = useState<Id<"squadSpecs"> | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [boardSettingsOpen, setBoardSettingsOpen] = useState(false);
  const [cronOpen, setCronOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activityPanelCollapsed, setActivityPanelCollapsed] = useState(true);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState("board");

  const handleCommandPaletteAction = useCallback((action: CommandPaletteAction) => {
    setCommandPaletteOpen(false);
    switch (action.type) {
      case "openTask":
        setSelectedTaskId(action.taskId);
        break;
      case "openAgent":
        setSelectedAgent(action.agentName);
        break;
      case "openSquad":
        setSelectedSquadId(action.squadId);
        break;
      case "openSettings":
        setSettingsOpen(true);
        break;
      case "openTags":
        setTagsOpen(true);
        break;
      case "openCronJobs":
        setCronOpen(true);
        break;
      case "openBoardSettings":
        setBoardSettingsOpen(true);
        break;
    }
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA") return;
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const parsedSearch = useMemo(() => parseSearch(searchQuery), [searchQuery]);
  const { openTerminals, closeAllTerminals, activeBoardId } = useBoard();
  const gatewaySleepRuntime = useGatewaySleepRuntime();
  const gatewaySleepCountdown = useGatewaySleepCountdown(gatewaySleepRuntime);
  const requestGatewaySleepMode = useGatewaySleepModeRequest();
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
  const gatewaySleepButtonLabel = gatewaySleepRuntime?.mode === "sleep" ? "Wake now" : "Sleep now";
  const gatewaySleepNextMode = gatewaySleepRuntime?.mode === "sleep" ? "active" : "sleep";

  return (
    <SidebarProvider defaultOpen={isXl} className="h-screen overflow-hidden">
      <AgentSidebar onSelectAgent={setSelectedAgent} onSelectSquad={setSelectedSquadId} />
      <SidebarInset className="h-screen min-w-0 overflow-hidden">
        <div className="flex h-screen flex-col overflow-hidden bg-background">
          <header className="flex h-14 items-center justify-between border-b border-border px-4">
            <div className="flex items-center gap-1.5 md:gap-3 shrink-0">
              <SidebarTrigger className="md:hidden" />
              <h1
                className={`text-base md:text-xl font-bold text-foreground whitespace-nowrap${openTerminals.length > 0 ? " cursor-pointer hover:text-muted-foreground transition-colors" : ""}`}
                onClick={openTerminals.length > 0 ? closeAllTerminals : undefined}
              >
                <span className="md:hidden">M</span>
                <span className="hidden md:inline">Open Control</span>
              </h1>
            </div>
            <div className="flex items-center gap-2 md:gap-3 flex-1 min-w-0 justify-center px-2 md:px-4 max-w-2xl">
              <BoardSelector onOpenSettings={() => setBoardSettingsOpen(true)} />
              <SearchBar
                onSearchChange={setSearchQuery}
                className="hidden sm:flex"
                placeholder="Create a task or press ⌘K..."
              />
            </div>
            <div className="flex items-center gap-1 sm:gap-2 shrink-0 ml-auto">
              <button
                aria-label="Toggle search"
                onClick={() => setMobileSearchOpen((prev) => !prev)}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors sm:hidden"
              >
                <Search className="h-4 w-4" />
              </button>
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

          {mobileSearchOpen && (
            <div className="border-b border-border px-4 py-2 sm:hidden">
              <SearchBar onSearchChange={setSearchQuery} />
            </div>
          )}

          <div className="border-b border-border px-4 py-3">
            <TaskInput />
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-4 pb-14 md:pb-4">
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
      <ActivityFeedPanel
        collapsed={activityPanelCollapsed}
        onCollapse={() => setActivityPanelCollapsed(true)}
      />
      <TaskDetailSheet
        taskId={selectedTaskId}
        onClose={() => setSelectedTaskId(null)}
        onTaskOpen={(taskId) => setSelectedTaskId(taskId)}
      />
      <AgentConfigSheet
        agentName={selectedAgent}
        onClose={() => setSelectedAgent(null)}
        onOpenSquad={(id) => setSelectedSquadId(id)}
      />
      <SquadDetailSheet
        squadId={selectedSquadId}
        boardId={activeBoardId ?? undefined}
        onClose={() => setSelectedSquadId(null)}
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
      <BoardSettingsSheet open={boardSettingsOpen} onClose={() => setBoardSettingsOpen(false)} />
      <CronJobsModal
        open={cronOpen}
        onClose={() => setCronOpen(false)}
        onTaskClick={(taskId) => {
          setCronOpen(false);
          setSelectedTaskId(taskId as Id<"tasks">);
        }}
      />
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onAction={handleCommandPaletteAction}
      />
      <MobileTabBar
        activeTab={mobileTab}
        onTabChange={(tab) => {
          setMobileTab(tab);
          if (tab === "search") {
            setMobileSearchOpen((prev) => !prev);
          } else if (tab === "activity") {
            setActivityPanelCollapsed((prev) => !prev);
          } else if (tab === "settings") {
            setSettingsOpen(true);
          }
        }}
      />
    </SidebarProvider>
  );
}

export function DashboardLayout() {
  const isXl = useMediaQuery("(min-width: 1280px)");
  const isHydrated = useHydrated();

  // Prevent flash of wrong layout during hydration
  if (!isHydrated) {
    return null;
  }

  return (
    <BoardProvider>
      <DashboardContent isXl={isXl} />
    </BoardProvider>
  );
}

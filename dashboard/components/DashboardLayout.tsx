"use client";

import { useEffect, useMemo, useState } from "react";
import { Id } from "../convex/_generated/dataModel";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AgentSidebar } from "@/components/AgentSidebar";
import { ActivityFeedPanel } from "@/components/ActivityFeedPanel";
import { TaskInput } from "@/components/TaskInput";
import { KanbanBoard } from "@/components/KanbanBoard";
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
import { Settings, Tag, Clock } from "lucide-react";
import { BoardProvider } from "@/components/BoardContext";
import { BoardSelector } from "@/components/BoardSelector";
import { BoardSettingsSheet } from "@/components/BoardSettingsSheet";
import { CronJobsModal } from "@/components/CronJobsModal";
import { SearchBar } from "@/components/SearchBar";
import { parseSearch } from "@/lib/searchParser";

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

export function DashboardLayout() {
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const isXl = useMediaQuery("(min-width: 1280px)");
  const [mounted, setMounted] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<Id<"tasks"> | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [boardSettingsOpen, setBoardSettingsOpen] = useState(false);
  const [cronOpen, setCronOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const parsedSearch = useMemo(() => parseSearch(searchQuery), [searchQuery]);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Prevent flash of wrong layout during hydration
  if (!mounted) {
    return null;
  }

  // Viewport < 1024px: show banner
  if (!isDesktop) {
    return (
      <div className="flex h-screen items-center justify-center bg-background p-8">
        <p className="text-center text-sm text-muted-foreground">
          Mission Control is designed for desktop browsers (1024px+)
        </p>
      </div>
    );
  }

  return (
    <BoardProvider>
      <SidebarProvider defaultOpen={isXl} className="h-screen overflow-hidden">
        <AgentSidebar />
        <SidebarInset className="h-screen min-w-0 overflow-hidden">
          <div className="flex h-screen flex-col overflow-hidden bg-background">
            <header className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <h1 className="text-2xl font-bold text-foreground">
                  Mission Control
                </h1>
                <BoardSelector onOpenSettings={() => setBoardSettingsOpen(true)} />
                <SearchBar onSearchChange={setSearchQuery} />
              </div>
              <div className="flex items-center gap-1">
                <button
                  aria-label="Open cron jobs"
                  onClick={() => setCronOpen(true)}
                  className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  <Clock className="h-5 w-5" />
                </button>
                <button
                  aria-label="Open tags"
                  onClick={() => setTagsOpen(true)}
                  className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  <Tag className="h-5 w-5" />
                </button>
                <button
                  aria-label="Open settings"
                  onClick={() => setSettingsOpen(true)}
                  className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  <Settings className="h-5 w-5" />
                </button>
              </div>
            </header>

            <div className="border-b border-border px-4 py-3">
              <TaskInput />
            </div>

            <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-4">
              <KanbanBoard
                onTaskClick={(taskId) => setSelectedTaskId(taskId)}
                search={parsedSearch}
              />
            </div>
          </div>
        </SidebarInset>
        <ActivityFeedPanel />
        <TaskDetailSheet
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
        />
        <Sheet open={settingsOpen} onOpenChange={setSettingsOpen}>
          <SheetContent side="right" className="w-[600px] sm:w-[600px] p-0">
            <SheetHeader className="sr-only">
              <SheetTitle>Settings</SheetTitle>
              <SheetDescription>Configure global system defaults</SheetDescription>
            </SheetHeader>
            <SettingsPanel />
          </SheetContent>
        </Sheet>
        <Sheet open={tagsOpen} onOpenChange={setTagsOpen}>
          <SheetContent side="right" className="w-[400px] sm:w-[400px] p-0">
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
    </BoardProvider>
  );
}

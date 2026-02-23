"use client";

import { useEffect, useState } from "react";
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
import { Settings, Tag } from "lucide-react";
import { BoardProvider } from "@/components/BoardContext";
import { BoardSelector } from "@/components/BoardSelector";
import { BoardSettingsSheet } from "@/components/BoardSettingsSheet";

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
      <SidebarProvider defaultOpen={isXl}>
        <AgentSidebar />
        <SidebarInset>
          <div className="flex h-screen flex-col overflow-hidden bg-background">
            <header className="border-b border-border px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-foreground">
                  Mission Control
                </h1>
                <BoardSelector onOpenSettings={() => setBoardSettingsOpen(true)} />
              </div>
              <div className="flex items-center gap-1">
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

            <div className="border-b border-border px-6 py-3">
              <TaskInput />
            </div>

            <div className="flex-1 overflow-hidden px-6 py-4 flex flex-col min-h-0">
              <KanbanBoard onTaskClick={(taskId) => setSelectedTaskId(taskId)} />
            </div>
          </div>
        </SidebarInset>
        <ActivityFeedPanel />
        <TaskDetailSheet
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
        />
        <Sheet open={settingsOpen} onOpenChange={setSettingsOpen}>
          <SheetContent side="right" className="w-[480px] sm:w-[480px] p-0">
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
      </SidebarProvider>
    </BoardProvider>
  );
}

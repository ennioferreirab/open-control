"use client";

import { lazy, Suspense, useState } from "react";
import { PanelRightClose, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ActivityFeed } from "@/features/activity/components/ActivityFeed";
import { useActivityFeedPanelState } from "@/features/activity/hooks/useActivityFeedPanelState";

const ChatPanel = lazy(() =>
  import("@/components/ChatPanel").then((mod) => ({ default: mod.ChatPanel })),
);

interface ActivityFeedPanelProps {
  collapsed: boolean;
  onCollapse: () => void;
}

export function ActivityFeedPanel({ collapsed, onCollapse }: ActivityFeedPanelProps) {
  const [activeTab, setActiveTab] = useState("chats");
  const { clearActivities } = useActivityFeedPanelState();

  if (collapsed) {
    return null;
  }

  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col overflow-hidden border-l border-border bg-muted transition-all duration-200 md:relative md:inset-auto md:z-auto md:shrink-0 ${activeTab === "chats" ? "md:w-[420px]" : "md:w-[280px]"}`}
    >
      <div className="flex h-[60px] items-center justify-between border-b border-border px-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Activity Feed
        </h2>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              if (window.confirm("Clear all activities?")) {
                void clearActivities();
              }
            }}
            aria-label="Clear all activities"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={onCollapse} aria-label="Hide activity feed">
            <PanelRightClose className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <Tabs
        defaultValue="chats"
        className="flex min-h-0 flex-1 flex-col"
        onValueChange={setActiveTab}
      >
        <div className="px-3 pt-2">
          <TabsList className="w-full">
            <TabsTrigger value="activity" className="flex-1 text-xs">
              Activity
            </TabsTrigger>
            <TabsTrigger value="chats" className="flex-1 text-xs">
              Chats
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent
          value="activity"
          className="m-0 flex-1 min-h-0 overflow-hidden data-[state=active]:flex flex-col"
        >
          <ActivityFeed />
        </TabsContent>
        <TabsContent
          value="chats"
          className="m-0 flex-1 min-h-0 overflow-hidden data-[state=active]:flex flex-col"
        >
          <Suspense
            fallback={
              <div className="flex-1 p-4">
                <p className="text-xs italic text-muted-foreground">Loading...</p>
              </div>
            }
          >
            <ChatPanel />
          </Suspense>
        </TabsContent>
      </Tabs>
    </div>
  );
}

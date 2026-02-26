"use client";

import { lazy, Suspense, useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ActivityFeed } from "@/components/ActivityFeed";

const ChatPanel = lazy(() =>
  import("@/components/ChatPanel").then((mod) => ({ default: mod.ChatPanel }))
);

export function ActivityFeedPanel() {
  const [collapsed, setCollapsed] = useState(true);

  if (collapsed) {
    return (
      <div className="flex h-screen w-12 shrink-0 flex-col border-l border-border bg-muted/70">
        <div className="flex items-center justify-center p-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCollapsed(false)}
            aria-label="Show activity feed"
          >
            <PanelRightOpen className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-[280px] shrink-0 flex-col overflow-hidden border-l border-border bg-muted">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Activity Feed
        </h2>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed(true)}
          aria-label="Hide activity feed"
        >
          <PanelRightClose className="h-4 w-4" />
        </Button>
      </div>
      <Tabs defaultValue="activity" className="flex flex-1 min-h-0 flex-col">
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
          className="flex-1 min-h-0 overflow-hidden flex flex-col m-0"
        >
          <ActivityFeed />
        </TabsContent>
        <TabsContent
          value="chats"
          className="flex-1 min-h-0 overflow-hidden flex flex-col m-0"
        >
          <Suspense
            fallback={
              <div className="flex-1 p-4">
                <p className="text-xs text-muted-foreground italic">
                  Loading...
                </p>
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

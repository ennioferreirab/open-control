"use client";

import { useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ActivityFeed } from "@/components/ActivityFeed";

export function ActivityFeedPanel() {
  const [collapsed, setCollapsed] = useState(false);

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
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <ActivityFeed />
      </div>
    </div>
  );
}

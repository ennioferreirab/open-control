"use client";

import { useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ActivityFeed } from "@/components/ActivityFeed";

export function ActivityFeedPanel() {
  const [collapsed, setCollapsed] = useState(false);

  // h-dvh bounds the panel to the dynamic viewport height (handles mobile browser chrome).
  // sticky top-0 keeps it anchored to the viewport top even if the page scrolls.
  if (collapsed) {
    return (
      <div className="sticky top-0 flex h-dvh flex-col border-l border-border bg-muted">
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
    <div className="sticky top-0 flex h-dvh w-[280px] flex-col overflow-hidden border-l border-border bg-muted">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-lg font-semibold text-foreground">Activity Feed</h2>
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

"use client";

import { cn } from "@/lib/utils";
import { FolderOpen, MessageCircle, PanelLeft, Zap } from "lucide-react";

export type MobileTab = "thread" | "plan" | "files" | "live";

interface MobileBottomNavProps {
  activeTab: MobileTab;
  onTabChange: (tab: MobileTab) => void;
  hasLiveSession?: boolean;
  fileCount?: number;
  className?: string;
}

const TABS = [
  { id: "thread" as const, label: "Thread", icon: MessageCircle },
  { id: "plan" as const, label: "Plan", icon: PanelLeft },
  { id: "files" as const, label: "Files", icon: FolderOpen },
  { id: "live" as const, label: "Live", icon: Zap },
];

export function MobileBottomNav({
  activeTab,
  onTabChange,
  hasLiveSession,
  fileCount,
  className,
}: MobileBottomNavProps) {
  return (
    <nav
      data-testid="mobile-bottom-nav"
      className={cn(
        "flex h-12 items-center justify-around border-t border-border bg-background",
        className,
      )}
    >
      {TABS.map((tab) => {
        const isActive = activeTab === tab.id;
        const isLive = tab.id === "live";
        const activeColor = isLive ? "text-success" : "text-primary";
        const accentColor = isLive ? "bg-success" : "bg-primary";
        const Icon = tab.icon;

        return (
          <button
            key={tab.id}
            data-testid={`tab-${tab.id}`}
            onClick={() => onTabChange(tab.id)}
            className={cn(
              "relative flex flex-1 flex-col items-center gap-0.5 py-1.5",
              isActive ? activeColor : "text-muted-foreground",
            )}
          >
            {isActive && (
              <span
                data-testid={`accent-${tab.id}`}
                className={cn("absolute left-0 right-0 top-0 h-0.5", accentColor)}
              />
            )}
            <span className="relative">
              <Icon className="h-[18px] w-[18px]" />
              {tab.id === "live" && hasLiveSession && !isActive && (
                <span
                  data-testid="live-dot"
                  className="absolute -right-1 -top-1 h-1.5 w-1.5 rounded-full bg-success"
                />
              )}
              {tab.id === "files" && fileCount != null && fileCount > 0 && (
                <span
                  data-testid="file-count"
                  className="absolute -right-2.5 -top-1.5 text-[8px] font-bold text-primary"
                >
                  {fileCount}
                </span>
              )}
            </span>
            <span className="text-[9px] font-semibold uppercase tracking-wider">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

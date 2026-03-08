"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { FeedItem } from "@/components/FeedItem";
import { motion } from "motion/react";
import { useActivityFeed } from "@/features/activity/hooks/useActivityFeed";

export function ActivityFeed() {
  const { activities, hasNewActivity, isReconnecting, scrollAreaRef, scrollToTop } =
    useActivityFeed();

  // Reconnecting state: had data before but now loading
  if (isReconnecting) {
    return (
      <div className="flex-1 p-4">
        <p className="text-xs text-muted-foreground italic">Reconnecting...</p>
      </div>
    );
  }

  // Loading state
  if (activities === undefined) return null;

  // Empty state
  if (activities.length === 0) {
    return (
      <div className="flex-1 p-4">
        <p className="text-sm text-muted-foreground italic">Waiting for activity...</p>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col" aria-live="polite">
      <ScrollArea ref={scrollAreaRef} className="flex-1">
        <div className="space-y-2 p-3">
          {activities.map((activity) => (
            <motion.div
              key={activity._id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              <FeedItem activity={activity} />
            </motion.div>
          ))}
          {activities.length >= 100 && (
            <p className="text-xs text-center text-muted-foreground py-2">
              Showing last 100 activities
            </p>
          )}
        </div>
      </ScrollArea>

      {hasNewActivity && (
        <button
          onClick={scrollToTop}
          className="absolute bottom-3 left-1/2 -translate-x-1/2
            rounded-full bg-blue-500 px-3 py-1 text-xs text-white
            shadow-md hover:bg-blue-600 transition-colors"
        >
          New activity
        </button>
      )}
    </div>
  );
}

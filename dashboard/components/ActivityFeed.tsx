"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useQuery } from "convex/react";
import { api } from "../convex/_generated/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FeedItem } from "./FeedItem";
import { motion } from "motion/react";

export function ActivityFeed() {
  const activities = useQuery(api.activities.listRecent);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [isAtTop, setIsAtTop] = useState(true);
  const [hasNewActivity, setHasNewActivity] = useState(false);
  // Track newest item id to detect new arrivals at steady state (count-based tracking breaks at 100 items)
  const prevNewestIdRef = useRef<string | undefined>(undefined);
  const hadDataRef = useRef(false);

  // Track whether we previously had data (for reconnection detection)
  if (activities && activities.length > 0) {
    hadDataRef.current = true;
  }

  // Capture the ScrollArea viewport element
  const scrollAreaRef = useCallback((node: HTMLDivElement | null) => {
    if (node) {
      const viewport = node.querySelector(
        "[data-radix-scroll-area-viewport]"
      ) as HTMLDivElement | null;
      if (viewport) {
        viewportRef.current = viewport;
      }
    }
  }, []);

  // Detect scroll position
  const handleScroll = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return;
    const atTop = el.scrollTop < 30;
    setIsAtTop(atTop);
    if (atTop) {
      setHasNewActivity(false);
    }
  }, []);

  // Attach scroll listener to viewport (handleScroll is stable — no need to re-register on data changes)
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    el.addEventListener("scroll", handleScroll);
    return () => el.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  // Auto-scroll to top when a new item arrives at the head of the feed
  useEffect(() => {
    if (!activities) return;
    const newestId = activities[0]?._id;
    if (newestId && newestId !== prevNewestIdRef.current && prevNewestIdRef.current !== undefined) {
      if (isAtTop) {
        requestAnimationFrame(() => {
          viewportRef.current?.scrollTo({ top: 0, behavior: "smooth" });
        });
      } else {
        setHasNewActivity(true);
      }
    }
    prevNewestIdRef.current = newestId;
  }, [activities, isAtTop]);

  const scrollToTop = () => {
    viewportRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    setHasNewActivity(false);
    setIsAtTop(true);
  };

  // Reconnecting state: had data before but now loading
  if (activities === undefined && hadDataRef.current) {
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

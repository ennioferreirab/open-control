"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Doc } from "@/convex/_generated/dataModel";

export interface ActivityFeedState {
  activities: Doc<"activities">[] | undefined;
  hasNewActivity: boolean;
  isAtTop: boolean;
  isReconnecting: boolean;
  scrollAreaRef: (node: HTMLDivElement | null) => void;
  scrollToTop: () => void;
}

export function useActivityFeed(): ActivityFeedState {
  const activities = useQuery(api.activities.listRecent);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [isAtTop, setIsAtTop] = useState(true);
  const [hasNewActivity, setHasNewActivity] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const prevNewestIdRef = useRef<string | undefined>(undefined);
  const hadDataRef = useRef(false);

  const scrollAreaRef = useCallback((node: HTMLDivElement | null) => {
    if (!node) return;

    const viewport = node.querySelector(
      "[data-radix-scroll-area-viewport]",
    ) as HTMLDivElement | null;

    if (viewport) {
      viewportRef.current = viewport;
    }
  }, []);

  const handleScroll = useCallback(() => {
    const element = viewportRef.current;
    if (!element) return;

    const atTop = element.scrollTop < 30;
    setIsAtTop(atTop);
    if (atTop) {
      setHasNewActivity(false);
    }
  }, []);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;

    element.addEventListener("scroll", handleScroll);
    return () => element.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  /* eslint-disable react-hooks/set-state-in-effect */
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
  /* eslint-enable react-hooks/set-state-in-effect */

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (activities && activities.length > 0) {
      hadDataRef.current = true;
      setIsReconnecting(false);
      return;
    }

    if (activities === undefined && hadDataRef.current) {
      setIsReconnecting(true);
    }
  }, [activities]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const scrollToTop = useCallback(() => {
    viewportRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    setHasNewActivity(false);
    setIsAtTop(true);
  }, []);

  return {
    activities,
    hasNewActivity,
    isAtTop,
    isReconnecting,
    scrollAreaRef,
    scrollToTop,
  };
}

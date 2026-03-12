"use client";

import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";

export interface ActivityFeedPanelState {
  clearActivities: () => Promise<void>;
}

export function useActivityFeedPanelState(): ActivityFeedPanelState {
  const clearActivitiesMutation = useMutation(api.activities.clearAll);

  return {
    clearActivities: async () => {
      await clearActivitiesMutation();
    },
  };
}

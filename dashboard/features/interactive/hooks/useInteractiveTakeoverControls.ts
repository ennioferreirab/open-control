"use client";

import { useState } from "react";
import { useMutation } from "convex/react";

import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

type TakeoverArgs = {
  sessionId: string;
  taskId: Id<"tasks">;
  stepId: Id<"steps">;
  agentName: string;
  provider: string;
};

type ManualDoneArgs = TakeoverArgs & {
  content: string;
};

export function useInteractiveTakeoverControls() {
  const requestHumanTakeover = useMutation(api.interactiveSessions.requestHumanTakeover);
  const resumeAgentControl = useMutation(api.interactiveSessions.resumeAgentControl);
  const markManualStepDone = useMutation(api.interactiveSessions.markManualStepDone);
  const [isRequestingTakeover, setIsRequestingTakeover] = useState(false);
  const [isResumingAgent, setIsResumingAgent] = useState(false);
  const [isMarkingDone, setIsMarkingDone] = useState(false);

  return {
    async requestTakeover(args: TakeoverArgs) {
      setIsRequestingTakeover(true);
      try {
        await requestHumanTakeover(args);
      } finally {
        setIsRequestingTakeover(false);
      }
    },
    async resumeAgent(args: TakeoverArgs) {
      setIsResumingAgent(true);
      try {
        await resumeAgentControl(args);
      } finally {
        setIsResumingAgent(false);
      }
    },
    async markDone(args: ManualDoneArgs) {
      setIsMarkingDone(true);
      try {
        await markManualStepDone(args);
      } finally {
        setIsMarkingDone(false);
      }
    },
    isRequestingTakeover,
    isResumingAgent,
    isMarkingDone,
  };
}

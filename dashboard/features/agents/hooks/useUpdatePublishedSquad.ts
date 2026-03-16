"use client";

import { useState } from "react";
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

type UpdatePublishedSquadStep = {
  key: string;
  title: string;
  type: "agent" | "human" | "checkpoint" | "review" | "system";
  description?: string;
  agentKey?: string;
  reviewSpecId?: string;
  onReject?: string;
  dependsOn: string[];
};

export interface UpdatePublishedSquadArgs {
  squadSpecId: Id<"squadSpecs">;
  graph: {
    squad: {
      name: string;
      displayName: string;
      description?: string;
      outcome?: string;
    };
    agents: Array<{
      key: string;
      name: string;
      role: string;
      displayName?: string;
      prompt?: string;
      model?: string;
      skills?: string[];
      soul?: string;
    }>;
    workflows: Array<{
      id: Id<"workflowSpecs">;
      key: string;
      name: string;
      exitCriteria?: string;
      steps: UpdatePublishedSquadStep[];
    }>;
  };
}

export interface UseUpdatePublishedSquadResult {
  isPublishing: boolean;
  publish: (args: UpdatePublishedSquadArgs) => Promise<Id<"squadSpecs"> | null>;
}

export function useUpdatePublishedSquad(): UseUpdatePublishedSquadResult {
  const [isPublishing, setIsPublishing] = useState(false);
  const publishMutation = useMutation(api.squadSpecs.updatePublishedGraph);

  const publish = async (args: UpdatePublishedSquadArgs): Promise<Id<"squadSpecs"> | null> => {
    setIsPublishing(true);
    try {
      return await publishMutation(args);
    } finally {
      setIsPublishing(false);
    }
  };

  return {
    isPublishing,
    publish,
  };
}

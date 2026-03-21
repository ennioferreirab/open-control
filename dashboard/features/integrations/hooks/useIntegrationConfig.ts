"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";

export type LinearConfigFormState = {
  apiKey: string;
  webhookSecret: string;
  boardId: string;
  enabled: boolean;
};

type BoardOption = {
  id: string;
  displayName: string;
};

export type UseIntegrationConfigReturn = {
  config: {
    _id: string;
    apiKey: string;
    webhookSecret?: string;
    boardId?: Id<"boards">;
    enabled: boolean;
  } | null;
  boards: BoardOption[];
  isLoading: boolean;
  formState: LinearConfigFormState;
  saving: boolean;
  saved: boolean;
  setFormState: React.Dispatch<React.SetStateAction<LinearConfigFormState>>;
  handleSave: () => Promise<void>;
  handleToggleEnabled: (enabled: boolean) => Promise<void>;
};

export function useIntegrationConfig(): UseIntegrationConfigReturn {
  const rawConfig = useQuery(api.integrations.getLinearConfig);
  const rawBoards = useQuery(api.boards.list);
  const upsertConfig = useMutation(api.integrations.upsertLinearConfig);
  const toggleEnabled = useMutation(api.integrations.toggleLinearEnabled);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const initializedRef = useRef(false);

  const [formState, setFormState] = useState<LinearConfigFormState>({
    apiKey: "",
    webhookSecret: "",
    boardId: "",
    enabled: false,
  });

  // Initialize form from server config on first load
  useEffect(() => {
    if (rawConfig !== undefined && !initializedRef.current) {
      initializedRef.current = true;
      if (rawConfig) {
        setFormState({
          apiKey: rawConfig.apiKey,
          webhookSecret: rawConfig.webhookSecret ?? "",
          boardId: rawConfig.boardId ?? "",
          enabled: rawConfig.enabled,
        });
      }
    }
  }, [rawConfig]);

  const isLoading = rawConfig === undefined || rawBoards === undefined;
  const config = rawConfig ?? null;
  const boards: BoardOption[] = (rawBoards ?? []).map((b) => ({
    id: b._id,
    displayName: b.displayName,
  }));

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await upsertConfig({
        apiKey: formState.apiKey,
        webhookSecret: formState.webhookSecret || undefined,
        boardId: formState.boardId ? (formState.boardId as Id<"boards">) : undefined,
        enabled: formState.enabled,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error("[IntegrationConfig] Save failed:", error);
      throw error;
    } finally {
      setSaving(false);
    }
  }, [upsertConfig, formState]);

  const handleToggleEnabled = useCallback(
    async (enabled: boolean) => {
      const previousEnabled = formState.enabled;
      setFormState((prev) => ({ ...prev, enabled }));
      try {
        await toggleEnabled({ enabled });
      } catch {
        // Revert optimistic update on failure
        setFormState((prev) => ({ ...prev, enabled: previousEnabled }));
      }
    },
    [toggleEnabled, formState.enabled],
  );

  return {
    config,
    boards,
    isLoading,
    formState,
    saving,
    saved,
    setFormState,
    handleSave,
    handleToggleEnabled,
  };
}

"use client";

import { useIntegrationConfig } from "@/features/integrations/hooks/useIntegrationConfig";
import { LinearConfigCard } from "./LinearConfigCard";
import { Skeleton } from "@/components/ui/skeleton";

export function IntegrationSettings() {
  const {
    config,
    boards,
    isLoading,
    formState,
    setFormState,
    saving,
    saved,
    handleSave,
    handleToggleEnabled,
  } = useIntegrationConfig();

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <LinearConfigCard
        formState={formState}
        setFormState={setFormState}
        boards={boards}
        onSave={handleSave}
        onToggleEnabled={handleToggleEnabled}
        saving={saving}
        saved={saved}
        hasExistingConfig={config !== null}
      />
    </div>
  );
}

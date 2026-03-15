"use client";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export type WizardProvider = "claude-code" | "codex";

interface ProviderOption {
  value: WizardProvider;
  label: string;
  enabled: boolean;
  disabledReason?: string;
}

const PROVIDERS: ProviderOption[] = [
  { value: "claude-code", label: "Claude Code", enabled: true },
  { value: "codex", label: "Codex", enabled: false, disabledReason: "Coming soon" },
];

interface ProviderSelectorProps {
  value: WizardProvider;
  onChange: (provider: WizardProvider) => void;
}

export function ProviderSelector({ value, onChange }: ProviderSelectorProps) {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex items-center gap-1">
        {PROVIDERS.map((opt) => {
          const isSelected = value === opt.value;
          const button = (
            <button
              key={opt.value}
              type="button"
              disabled={!opt.enabled}
              onClick={() => opt.enabled && onChange(opt.value)}
              className={[
                "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                isSelected && opt.enabled
                  ? "bg-zinc-100 text-zinc-900 dark:bg-zinc-700 dark:text-zinc-100"
                  : "",
                !isSelected && opt.enabled
                  ? "text-zinc-500 hover:text-zinc-300 dark:text-zinc-400 dark:hover:text-zinc-200"
                  : "",
                !opt.enabled
                  ? "cursor-not-allowed text-zinc-600 opacity-50 dark:text-zinc-500"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {opt.label}
            </button>
          );

          if (!opt.enabled && opt.disabledReason) {
            return (
              <Tooltip key={opt.value}>
                <TooltipTrigger asChild>{button}</TooltipTrigger>
                <TooltipContent side="bottom">{opt.disabledReason}</TooltipContent>
              </Tooltip>
            );
          }

          return button;
        })}
      </div>
    </TooltipProvider>
  );
}

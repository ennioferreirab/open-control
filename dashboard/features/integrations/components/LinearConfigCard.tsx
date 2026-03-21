"use client";

import { useCallback, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Check, Copy } from "lucide-react";
import type { LinearConfigFormState } from "@/features/integrations/hooks/useIntegrationConfig";

const NO_BOARD_VALUE = "__none__";

interface BoardOption {
  id: string;
  displayName: string;
}

interface LinearConfigCardProps {
  formState: LinearConfigFormState;
  setFormState: React.Dispatch<React.SetStateAction<LinearConfigFormState>>;
  boards: BoardOption[];
  onSave: () => Promise<void>;
  onToggleEnabled: (enabled: boolean) => Promise<void>;
  saving: boolean;
  saved: boolean;
  hasExistingConfig: boolean;
}

export function LinearConfigCard({
  formState,
  setFormState,
  boards,
  onSave,
  onToggleEnabled,
  saving,
  saved,
  hasExistingConfig,
}: LinearConfigCardProps) {
  const [copied, setCopied] = useState(false);

  const webhookUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/api/integrations/linear/webhook`
      : "/api/integrations/linear/webhook";

  const handleCopyWebhook = useCallback(async () => {
    await navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [webhookUrl]);

  const handleBoardChange = useCallback(
    (value: string) => {
      setFormState((prev) => ({
        ...prev,
        boardId: value === NO_BOARD_VALUE ? "" : value,
      }));
    },
    [setFormState],
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <CardTitle className="text-base">Linear</CardTitle>
            <CardDescription className="text-xs">
              Sync Linear issues as tasks on a board
            </CardDescription>
          </div>
          {hasExistingConfig && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {formState.enabled ? "Enabled" : "Disabled"}
              </span>
              <Switch
                checked={formState.enabled}
                onCheckedChange={(checked) => {
                  void onToggleEnabled(checked);
                }}
                aria-label="Toggle Linear integration"
              />
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="linear-api-key" className="text-sm">
            API Key
          </Label>
          <Input
            id="linear-api-key"
            type="password"
            placeholder="lin_api_••••••••"
            value={formState.apiKey}
            onChange={(e) => setFormState((prev) => ({ ...prev, apiKey: e.target.value }))}
          />
          <p className="text-xs text-muted-foreground">
            Personal API key from Linear Settings → API.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="linear-webhook-secret" className="text-sm">
            Webhook Secret
          </Label>
          <Input
            id="linear-webhook-secret"
            type="password"
            placeholder="Webhook signing secret"
            value={formState.webhookSecret}
            onChange={(e) => setFormState((prev) => ({ ...prev, webhookSecret: e.target.value }))}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="linear-board" className="text-sm">
            Sync Board
          </Label>
          <Select value={formState.boardId || NO_BOARD_VALUE} onValueChange={handleBoardChange}>
            <SelectTrigger id="linear-board">
              <SelectValue placeholder="Select a board" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_BOARD_VALUE}>No board selected</SelectItem>
              {boards.map((board) => (
                <SelectItem key={board.id} value={board.id}>
                  {board.displayName}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Linear issues will be created as tasks on this board.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label className="text-sm">Webhook URL</Label>
          <div className="flex gap-2">
            <Input
              readOnly
              value={webhookUrl}
              className="font-mono text-xs bg-muted cursor-default"
              aria-label="Webhook URL"
            />
            <Button
              variant="outline"
              size="icon"
              aria-label="Copy webhook URL"
              onClick={() => {
                void handleCopyWebhook();
              }}
              className="shrink-0"
            >
              {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Register this URL as a webhook in Linear Settings → API → Webhooks.
          </p>
        </div>

        <div className="flex items-center justify-between pt-1">
          {!hasExistingConfig && (
            <div className="flex items-center gap-2">
              <Switch
                checked={formState.enabled}
                onCheckedChange={(checked) =>
                  setFormState((prev) => ({ ...prev, enabled: checked }))
                }
                aria-label="Enable Linear integration on save"
              />
              <span className="text-sm text-muted-foreground">Enable on save</span>
            </div>
          )}
          <div className="flex items-center gap-2 ml-auto">
            {saved && <Check className="h-4 w-4 text-green-500" />}
            <Button
              onClick={() => {
                void onSave();
              }}
              disabled={saving || !formState.apiKey.trim()}
              size="sm"
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

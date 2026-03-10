/**
 * Polling & Sleep settings field definitions.
 *
 * Single source of truth for key names, defaults, labels, and bounds.
 * Used by useSettingsPanelState (defaults) and SettingsPanel (UI fields).
 *
 * IMPORTANT: Keep in sync with mc/runtime/gateway.py POLLING_DEFAULTS and
 * POLLING_BOUNDS — the Python side reads these at gateway startup and
 * applies the same bounds server-side.
 */

export interface PollingField {
  key: string;
  label: string;
  defaultValue: string;
  min: number;
  max: number;
  group: "gateway" | "component";
}

export const POLLING_FIELDS: PollingField[] = [
  {
    key: "gateway_active_poll_seconds",
    label: "Gateway: Active Poll Interval (s)",
    defaultValue: "5",
    min: 1,
    max: 60,
    group: "gateway",
  },
  {
    key: "gateway_sleep_poll_seconds",
    label: "Gateway: Sleep Poll Interval (s)",
    defaultValue: "300",
    min: 10,
    max: 3600,
    group: "gateway",
  },
  {
    key: "gateway_auto_sleep_seconds",
    label: "Gateway: Auto-Sleep After (s)",
    defaultValue: "300",
    min: 30,
    max: 3600,
    group: "gateway",
  },
  {
    key: "chat_active_poll_seconds",
    label: "Chat: Active Poll Interval (s)",
    defaultValue: "5",
    min: 1,
    max: 60,
    group: "component",
  },
  {
    key: "chat_sleep_poll_seconds",
    label: "Chat: Sleep Poll Interval (s)",
    defaultValue: "60",
    min: 5,
    max: 600,
    group: "component",
  },
  {
    key: "mention_poll_seconds",
    label: "Mention: Poll Interval (s)",
    defaultValue: "10",
    min: 1,
    max: 120,
    group: "component",
  },
  {
    key: "timeout_check_seconds",
    label: "Timeout Check Interval (s)",
    defaultValue: "60",
    min: 10,
    max: 600,
    group: "component",
  },
];

/** Polling defaults as a Record for use in useSettingsPanelState. */
export const POLLING_DEFAULTS: Record<string, string> = Object.fromEntries(
  POLLING_FIELDS.map((f) => [f.key, f.defaultValue]),
);

"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { X, Trash2, ExternalLink } from "lucide-react";
import { parseCronToTable } from "@/lib/cronParser";

interface CronSchedule {
  kind: "at" | "every" | "cron";
  atMs: number | null;
  everyMs: number | null;
  expr: string | null;
  tz: string | null;
}

interface CronPayload {
  kind: string;
  message: string;
  deliver: boolean;
  channel: string | null;
  to: string | null;
  taskId: string | null;
  agent: string | null;
}

interface CronJobState {
  nextRunAtMs: number | null;
  lastRunAtMs: number | null;
  lastStatus: "ok" | "error" | "skipped" | null;
  lastError: string | null;
  lastTaskId: string | null;
}

interface CronJob {
  id: string;
  name: string;
  enabled: boolean;
  schedule: CronSchedule;
  payload: CronPayload;
  state: CronJobState;
  createdAtMs: number;
  updatedAtMs: number;
  deleteAfterRun: boolean;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onTaskClick: (taskId: string) => void;
}

function normalizeChannelsPayload(data: unknown): string[] {
  if (
    typeof data === "object" &&
    data !== null &&
    "channels" in data &&
    Array.isArray((data as { channels?: unknown }).channels)
  ) {
    return (data as { channels: unknown[] }).channels.filter(
      (channel): channel is string => typeof channel === "string" && channel.length > 0,
    );
  }
  return ["mc"];
}

function formatSchedule(schedule: CronSchedule): string {
  const tz = schedule.tz ? ` (${schedule.tz})` : "";
  if (schedule.kind === "every" && schedule.everyMs) {
    const s = schedule.everyMs / 1000;
    if (s < 60) return `every ${s}s${tz}`;
    if (s < 3600) return `every ${Math.round(s / 60)}min${tz}`;
    return `every ${Math.round(s / 3600)}hr${tz}`;
  }
  if (schedule.kind === "cron" && schedule.expr) {
    return `cron: ${schedule.expr}${tz}`;
  }
  if (schedule.kind === "at" && schedule.atMs) {
    return `at: ${new Date(schedule.atMs).toLocaleString()}${tz}`;
  }
  return "—";
}

function formatRelative(ms: number | null): string {
  if (ms == null) return "—";
  const diff = ms - Date.now();
  const abs = Math.abs(diff);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (abs < 60_000) return rtf.format(Math.round(diff / 1000), "seconds");
  if (abs < 3_600_000) return rtf.format(Math.round(diff / 60_000), "minutes");
  if (abs < 86_400_000)
    return rtf.format(Math.round(diff / 3_600_000), "hours");
  return rtf.format(Math.round(diff / 86_400_000), "days");
}

function StatusBadge({
  status,
  error,
}: {
  status: "ok" | "error" | "skipped";
  error: string | null;
}) {
  const cls: Record<string, string> = {
    ok: "text-green-600 bg-green-50 border-green-200",
    error: "text-red-600 bg-red-50 border-red-200",
    skipped: "text-muted-foreground bg-muted border-border",
  };
  const badge = (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium border ${cls[status] ?? cls.skipped}`}
    >
      {status}
    </span>
  );
  if (status === "error" && error) {
    return (
      <span title={error} className="cursor-help">
        {badge}
      </span>
    );
  }
  return badge;
}

export function CronJobsModal({ open, onClose, onTaskClick }: Props) {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDeleteJob, setConfirmDeleteJob] = useState<CronJob | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [enabledChannels, setEnabledChannels] = useState<string[]>([]);
  const [editingJob, setEditingJob] = useState<string | null>(null);
  const [editChannel, setEditChannel] = useState<string>("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const resolveTaskId = (job: CronJob) => job.state.lastTaskId ?? job.payload.taskId;

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setJobs([]);
    setLoading(true);
    setError(null);
    fetch("/api/cron")
      .then((res) => {
        if (!res.ok) throw new Error("server error");
        return res.json() as Promise<{ jobs: CronJob[] }>;
      })
      .then((data) => {
        if (!cancelled) {
          setJobs(data.jobs);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Failed to load cron jobs.");
          setLoading(false);
        }
      });
    fetch("/api/channels")
      .then((res) =>
        res.ok
          ? (res.json() as Promise<unknown>)
          : ({ channels: ["mc"] } satisfies { channels: string[] }),
      )
      .then((data) => {
        if (!cancelled) {
          setEnabledChannels(normalizeChannelsPayload(data));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setEnabledChannels(["mc"]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  async function handleDelete() {
    if (!confirmDeleteJob) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const res = await fetch(`/api/cron/${confirmDeleteJob.id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("failed");
      setJobs((prev) => prev.filter((j) => j.id !== confirmDeleteJob.id));
      setConfirmDeleteJob(null);
    } catch {
      setDeleteError("Failed to delete. Please try again.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-4xl w-full max-h-[80vh] flex flex-col p-0 gap-0 [&>button]:hidden">
        <DialogHeader className="flex flex-row items-center justify-between px-6 py-4 border-b shrink-0">
          <div className="flex items-center gap-2">
            <DialogTitle className="text-base font-medium">
              Scheduled Cron Jobs
            </DialogTitle>
            <div className="flex items-center gap-1 ml-4">
              {enabledChannels.map((ch) => (
                <Badge key={ch} variant="outline" className="text-[10px] px-1.5 py-0">
                  {ch}
                </Badge>
              ))}
            </div>
          </div>
          <Button
            aria-label="Close cron jobs"
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-auto p-4">
          {loading && (
            <div className="flex flex-col gap-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="h-10 bg-muted animate-pulse rounded"
                />
              ))}
            </div>
          )}

          {error && (
            <p className="text-sm text-red-500 text-center py-8">{error}</p>
          )}

          {!loading && !error && jobs.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No scheduled jobs. Agents can create cron jobs using the{" "}
              <code className="font-mono">cron</code> tool.
            </p>
          )}

          {!loading && !error && jobs.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground text-xs">
                  <th className="text-left pb-2 pr-4 font-medium">Name</th>
                  <th className="text-left pb-2 pr-4 font-medium">Agent</th>
                  <th className="text-left pb-2 pr-4 font-medium">Schedule</th>
                  <th className="text-left pb-2 pr-4 font-medium">Channel</th>
                  <th className="text-left pb-2 pr-4 font-medium">Last Run</th>
                  <th className="text-left pb-2 pr-4 font-medium">Next Run</th>
                  <th className="text-left pb-2 pr-4 font-medium">Last Status</th>
                  <th className="text-left pb-2 pr-4 font-medium">Task</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody>
                {jobs.map((job, idx) => (
                  <tr key={job.id || idx} className="border-b last:border-0">
                    <td className="py-2 pr-4">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{job.name}</span>
                        <Badge
                          variant={job.enabled ? "default" : "secondary"}
                          className="text-xs"
                        >
                          {job.enabled ? "enabled" : "disabled"}
                        </Badge>
                      </div>
                    </td>
                    <td className="py-2 pr-4 text-xs text-muted-foreground">
                      {job.payload.agent ?? "—"}
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground text-xs">
                      <div className="font-mono">
                        {formatSchedule(job.schedule)}
                      </div>
                      {job.schedule.kind === "cron" && job.schedule.expr && (() => {
                        const parsed = parseCronToTable(job.schedule.expr);
                        if (!parsed) return null;
                        return (
                          <div className="mt-1 grid grid-cols-3 gap-x-3 text-[11px] text-muted-foreground">
                            <div>
                              <span className="font-medium text-foreground/70">Days</span>
                              <div>{parsed.days}</div>
                            </div>
                            <div>
                              <span className="font-medium text-foreground/70">Hours</span>
                              <div>{parsed.hours}</div>
                            </div>
                            <div>
                              <span className="font-medium text-foreground/70">Minutes</span>
                              <div>{parsed.minutes}</div>
                            </div>
                          </div>
                        );
                      })()}
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground text-xs">
                      {editingJob === job.id ? (
                        <div className="flex flex-col gap-1">
                          <select
                            className="text-xs border rounded px-1 py-0.5 bg-background"
                            value={editChannel}
                            onChange={(e) => setEditChannel(e.target.value)}
                          >
                            <option value="">— none —</option>
                            {enabledChannels.map((ch) => (
                              <option key={ch} value={ch}>{ch}</option>
                            ))}
                          </select>
                          <div className="flex gap-1">
                            <button
                              className="text-[10px] text-green-600 hover:underline disabled:opacity-50"
                              disabled={saving}
                              onClick={async () => {
                                setSaving(true);
                                setSaveError(null);
                                try {
                                  const res = await fetch(`/api/cron/${job.id}`, {
                                    method: "PATCH",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({ channel: editChannel || null }),
                                  });
                                  if (res.ok) {
                                    setJobs((prev) =>
                                      prev.map((j) =>
                                        j.id === job.id
                                          ? { ...j, payload: { ...j.payload, channel: editChannel || null } }
                                          : j,
                                      ),
                                    );
                                    setEditingJob(null);
                                  } else {
                                    setSaveError("Failed to save.");
                                  }
                                } finally {
                                  setSaving(false);
                                }
                              }}
                            >
                              {saving ? "..." : "save"}
                            </button>
                            <button
                              className="text-[10px] text-muted-foreground hover:underline"
                              onClick={() => { setEditingJob(null); setSaveError(null); }}
                            >
                              cancel
                            </button>
                          </div>
                          {saveError && <p className="text-[10px] text-red-500">{saveError}</p>}
                        </div>
                      ) : (
                        <button
                          className="hover:underline text-left"
                          onClick={() => {
                            setEditingJob(job.id);
                            setEditChannel(job.payload.channel ?? "");
                            setSaveError(null);
                          }}
                        >
                          {job.payload.channel ? (
                            <span className="flex items-center gap-1" title={job.payload.channel}>
                              {job.payload.channel === "telegram" ? (
                                <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4 text-[#229ED9]">
                                  <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                                </svg>
                              ) : job.payload.channel === "mc" ? (
                                <span className="inline-flex items-center justify-center h-5 px-1.5 rounded text-[10px] font-bold bg-foreground/10 text-foreground/70">MC</span>
                              ) : (
                                <span className="text-xs">{job.payload.channel}</span>
                              )}
                            </span>
                          ) : (
                            <span>—</span>
                          )}
                        </button>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground text-xs">
                      {formatRelative(job.state.lastRunAtMs)}
                    </td>
                    <td className="py-2 pr-4 text-muted-foreground text-xs">
                      {job.enabled
                        ? formatRelative(job.state.nextRunAtMs)
                        : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      {job.state.lastStatus ? (
                        <StatusBadge
                          status={job.state.lastStatus}
                          error={job.state.lastError}
                        />
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      {resolveTaskId(job) ? (
                        <Button variant="ghost" size="icon" aria-label="Open related task"
                          className="h-7 w-7 text-muted-foreground hover:text-foreground"
                          onClick={() => { onClose(); onTaskClick(resolveTaskId(job)!); }}>
                          <ExternalLink className="h-3.5 w-3.5" />
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="py-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${job.name}`}
                        className="h-7 w-7 text-muted-foreground hover:text-red-500"
                        onClick={() => {
                          setDeleteError(null);
                          setConfirmDeleteJob(job);
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </DialogContent>

      <AlertDialog
        open={confirmDeleteJob !== null}
        onOpenChange={(o) => {
          if (!o) {
            setConfirmDeleteJob(null);
            setDeleteError(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete &quot;{confirmDeleteJob?.name}&quot;?</AlertDialogTitle>
            <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          {deleteError && (
            <p className="text-xs text-red-500 -mt-2">{deleteError}</p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-red-600 hover:bg-red-700"
            >
              {deleting ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  );
}

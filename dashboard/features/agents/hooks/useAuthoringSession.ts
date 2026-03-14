"use client";

import { useCallback, useState } from "react";
import type { AuthoringMode, AuthoringPhase } from "@/features/agents/lib/authoringContract";
import { parseAuthoringResponse } from "@/features/agents/lib/authoringContract";

export interface TranscriptMessage {
  role: "user" | "assistant";
  content: string;
}

export interface UseAuthoringSessionReturn {
  /** Current canonical phase. */
  phase: AuthoringPhase;
  /** Full conversation transcript. */
  transcript: TranscriptMessage[];
  /** Accumulated draft graph (merged from all patches). */
  draftGraph: Record<string, unknown>;
  /** Whether a request is in flight. */
  isLoading: boolean;
  /** Error from the last request, if any. */
  error: string | null;
  /** Readiness score (0–1) from the last LLM response. */
  readiness: number;
  /** Send a user message and update session state. */
  sendMessage: (content: string) => Promise<void>;
  /** Manually patch the accumulated draft graph (for user edits). */
  patchDraftGraph: (patch: Record<string, unknown>) => void;
  /** Reset session to initial state. */
  reset: () => void;
}

const ENDPOINT_MAP: Record<AuthoringMode, string> = {
  agent: "/api/authoring/agent-wizard",
  squad: "/api/authoring/squad-wizard",
};

/**
 * Shared hook for managing an authoring session (agent or squad).
 *
 * Stores transcript, current phase, and merged draft graph.
 * Calls the appropriate backend endpoint and updates state from
 * the structured AuthoringResponse.
 */
export function useAuthoringSession(mode: AuthoringMode): UseAuthoringSessionReturn {
  const [phase, setPhase] = useState<AuthoringPhase>("discovery");
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [draftGraph, setDraftGraph] = useState<Record<string, unknown>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readiness, setReadiness] = useState(0);

  const sendMessage = useCallback(
    async (content: string) => {
      setIsLoading(true);
      setError(null);

      const userMessage: TranscriptMessage = { role: "user", content };
      const updatedTranscript = [...transcript, userMessage];
      setTranscript(updatedTranscript);

      try {
        const response = await fetch(ENDPOINT_MAP[mode], {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: updatedTranscript.map((m) => ({ role: m.role, content: m.content })),
            phase,
          }),
        });

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({}));
          throw new Error((errBody as { error?: string }).error ?? `HTTP ${response.status}`);
        }

        const raw = await response.json();
        const parsed = parseAuthoringResponse(raw);

        const assistantMessage: TranscriptMessage = {
          role: "assistant",
          content: parsed.assistantMessage,
        };

        setTranscript((prev) => [...prev, assistantMessage]);
        setPhase(parsed.phase);
        // Merge draft graph patch into accumulated draft graph
        setDraftGraph((prev) => ({
          ...prev,
          ...(parsed.draftGraphPatch as Record<string, unknown>),
        }));
        setReadiness(parsed.readiness);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        // Revert to last known state (remove the optimistically added user message on error)
        setTranscript((prev) => prev.slice(0, prev.length - 1));
      } finally {
        setIsLoading(false);
      }
    },
    [mode, phase, transcript],
  );

  const patchDraftGraph = useCallback((patch: Record<string, unknown>) => {
    setDraftGraph((prev) => ({ ...prev, ...patch }));
  }, []);

  const reset = useCallback(() => {
    setPhase("discovery");
    setTranscript([]);
    setDraftGraph({});
    setError(null);
    setIsLoading(false);
    setReadiness(0);
  }, []);

  return {
    phase,
    transcript,
    draftGraph,
    isLoading,
    error,
    readiness,
    sendMessage,
    patchDraftGraph,
    reset,
  };
}

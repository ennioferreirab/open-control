# Scaling Decisions

Architectural decisions that work for the current scale but may need revisiting as the system grows. Each entry documents the decision, its limits, the files involved, and a note on what a future solution might look like.

---

## 1. Convex 1MB string limit — overflow to filesystem

**Decision:** Convex has a hard, non-configurable 1MB limit per string value. Large content that still touches Convex (for example `messages.content`) is capped at 900KB. When exceeded, the full content is saved to the task's filesystem (`~/.nanobot/tasks/{id}/output/_overflow/`) and the Convex field stores a truncated version with a pointer to the file. Live transcript bytes no longer go to Convex; they live under `OPEN_CONTROL_LIVE_HOME`.

**Why this works now:** Claude's output token limit (~200K tokens ≈ ~800KB) means most results fit under 900KB. The overflow path is a safety net, not a common path.

**Limits:**
- Overflow files are local to the machine — not accessible from other nodes or the dashboard browser directly.
- File-backed Live transcripts are local-node storage only; deleting the dedicated live volume removes transcript history but preserves Convex metadata.
- Per-key truncation in rawJson (`_truncate_large_values`) uses a 16KB threshold per string value, which may be too aggressive or too lenient depending on the provider.

**Future direction:** Replace local-node filesystem storage with shared object storage (Convex file storage or S3) so Live and overflow content remain available across nodes. Thread already uses filesystem overflow markers; Live is fully file-backed now.

**Files involved:**

| File | Lines | Role |
|------|-------|------|
| `mc/bridge/overflow.py` | all | `safe_string_for_convex()` — truncation + file backup utility |
| `mc/contexts/interactive/activity_service.py` | `append_event`, `_resolve_overflow_dir` | Centralized overflow protection and file-backed Live persistence |
| `mc/contexts/interactive/live_store.py` | all | Append-only Live transcript store under `OPEN_CONTROL_LIVE_HOME` |
| `mc/contexts/provider_cli/providers/claude_code.py` | `_truncate_large_values` | Per-key truncation of large dict values before JSON serialization |
| `mc/bridge/repositories/messages.py` | `send_message`, `post_*` helpers | Thread message overflow protection for Convex-backed messages |
| `dashboard/features/interactive/components/ProviderLiveEventRow.tsx` | `hasTruncationMarker`, truncated badge | Visual "Truncated" badge when content contains overflow marker |

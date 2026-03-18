# Scaling Decisions

Architectural decisions that work for the current scale but may need revisiting as the system grows. Each entry documents the decision, its limits, the files involved, and a note on what a future solution might look like.

---

## 1. Convex 1MB string limit — overflow to filesystem

**Decision:** Convex has a hard, non-configurable 1MB limit per string value. Large content (rawText, rawJson in sessionActivityLog; content in messages) is capped at 900KB. When exceeded, the full content is saved to the task's filesystem (`~/.nanobot/tasks/{id}/output/_overflow/`) and the Convex field stores a truncated version with a pointer to the file.

**Why this works now:** Claude's output token limit (~200K tokens ≈ ~800KB) means most results fit under 900KB. The overflow path is a safety net, not a common path.

**Limits:**
- Overflow files are local to the machine — not accessible from other nodes or the dashboard browser directly.
- The `messages.content` field (Thread) does not yet have overflow protection (only sessionActivityLog fields do).
- Per-key truncation in rawJson (`_truncate_large_values`) uses a 16KB threshold per string value, which may be too aggressive or too lenient depending on the provider.

**Future direction:** Replace Convex string storage for large content with file-backed storage (Convex file storage or S3). The Live panel and Thread would read content from file references instead of inline strings. This would remove all size limits and reduce Convex document sizes.

**Files involved:**

| File | Lines | Role |
|------|-------|------|
| `mc/bridge/overflow.py` | all | `safe_string_for_convex()` — truncation + file backup utility |
| `mc/contexts/interactive/activity_service.py` | `append_event`, `_resolve_overflow_dir` | Centralized overflow protection for all runner strategies (nanobot + provider-cli) |
| `mc/contexts/provider_cli/providers/claude_code.py` | `_truncate_large_values` | Per-key truncation of large dict values before JSON serialization |
| `dashboard/convex/sessionActivityLog.ts` | `append` handler | rawText and rawJson stored without truncation (overflow handled upstream in Python) |
| `dashboard/features/interactive/components/ProviderLiveEventRow.tsx` | `hasTruncationMarker`, truncated badge | Visual "Truncated" badge when content contains overflow marker |

**Related concern:** Thread messages (`messages.content`) go through `mc/bridge/repositories/messages.py` and `mc/contexts/execution/executor.py` — these do not yet use `safe_string_for_convex`. Adding overflow protection there would complete the coverage.

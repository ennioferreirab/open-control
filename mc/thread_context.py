"""Thread context builder for agent prompt injection.

Builds the thread context that agents receive when starting a step.
Handles 20-message truncation (NFR5), predecessor completion message
injection, artifact formatting, and latest user message separation.

Extracted from executor.py _build_thread_context() to support
step-aware context building while preserving backward compatibility.
"""

from __future__ import annotations

from typing import Any

MAX_THREAD_MESSAGES = 20
MAX_DIFF_LENGTH = 2000


class ThreadContextBuilder:
    """Builds formatted thread context for agent prompt injection."""

    def build(
        self,
        messages: list[dict[str, Any]],
        max_messages: int = MAX_THREAD_MESSAGES,
        predecessor_step_ids: list[str] | None = None,
    ) -> str:
        """Build thread context string for agent injection.

        Args:
            messages: Thread messages in chronological order (snake_case keys).
            max_messages: Truncation window size (default 20, NFR5).
            predecessor_step_ids: Step IDs of direct blockedBy predecessors.
                When provided, their completion messages are always included.
                When None, falls back to legacy behavior.

        Returns:
            Formatted context string, or "" if no relevant context.
        """
        if not messages:
            return ""

        predecessor_ids = set(predecessor_step_ids or [])

        # Legacy behavior: when no predecessor IDs provided, preserve the
        # has_user_messages guard for backward compatibility (AC #7).
        if not predecessor_ids:
            return self._build_legacy(messages, max_messages)

        # Step-aware behavior: always build context if predecessors exist,
        # even without user messages (AC #3).
        return self._build_step_aware(messages, max_messages, predecessor_ids)

    def _build_legacy(
        self, messages: list[dict[str, Any]], max_messages: int
    ) -> str:
        """Legacy context building — mirrors original _build_thread_context().

        Returns empty string if no user messages exist (backward compat).
        """
        # Only inject context if there are user messages (multi-turn interaction)
        has_user_messages = any(
            m.get("author_type") == "user" or m.get("message_type") == "user_message"
            for m in messages
        )
        if not has_user_messages:
            return ""

        return self._format_context(messages, max_messages, predecessor_ids=set())

    def _build_step_aware(
        self,
        messages: list[dict[str, Any]],
        max_messages: int,
        predecessor_ids: set[str],
    ) -> str:
        """Step-aware context building — always includes predecessor completions.

        When predecessor messages fall outside the 20-message window they are
        injected as a [Predecessor Context] preamble section.
        """
        # Check if there are any predecessor completion messages at all
        predecessor_msgs = [
            m
            for m in messages
            if m.get("step_id") in predecessor_ids
            and m.get("type") == "step_completion"
        ]

        has_user_messages = any(
            m.get("author_type") == "user" or m.get("message_type") == "user_message"
            for m in messages
        )

        # No predecessors found and no user messages — nothing useful to inject
        if not predecessor_msgs and not has_user_messages:
            return ""

        return self._format_context(messages, max_messages, predecessor_ids)

    def _format_context(
        self,
        messages: list[dict[str, Any]],
        max_messages: int,
        predecessor_ids: set[str],
    ) -> str:
        """Core formatting logic shared by both legacy and step-aware paths."""
        total = len(messages)

        # Determine the 20-message window
        if total > max_messages:
            window = messages[-max_messages:]
            omitted_count = total - max_messages
        else:
            window = messages
            omitted_count = 0

        # Identify window messages by their index in the original list
        window_start_idx = total - len(window)

        # Identify predecessor messages that fall OUTSIDE the window
        predecessors_outside: list[tuple[int, dict[str, Any]]] = []
        if predecessor_ids:
            for orig_idx, m in enumerate(messages):
                if (
                    m.get("step_id") in predecessor_ids
                    and m.get("type") == "step_completion"
                    and orig_idx < window_start_idx
                ):
                    predecessors_outside.append((orig_idx, m))

        # Adjust omission count: predecessors shown in preamble are not truly
        # omitted from the agent's view, so subtract them from the note.
        effective_omitted = omitted_count - len(predecessors_outside)

        # Find the latest user message in the WINDOW
        latest_user_idx_in_window = -1
        for i in range(len(window) - 1, -1, -1):
            m = window[i]
            if m.get("author_type") == "user" or m.get("message_type") == "user_message":
                latest_user_idx_in_window = i
                break

        result_parts: list[str] = []

        # 1. [Predecessor Context] preamble for out-of-window predecessor messages
        if predecessors_outside:
            preamble_lines: list[str] = []
            for _, m in predecessors_outside:
                preamble_lines.append(self._format_message(m))
            result_parts.append("[Predecessor Context]\n" + "\n".join(preamble_lines))

        # 2. Omission note (when truncated) + thread history window
        thread_lines: list[str] = []
        if effective_omitted > 0:
            thread_lines.append(f"({effective_omitted} earlier messages omitted)")

        # 3. [Thread History] — window messages minus the latest user message
        for i, m in enumerate(window):
            if i == latest_user_idx_in_window:
                continue
            thread_lines.append(self._format_message(m))

        if thread_lines:
            result_parts.append("[Thread History]\n" + "\n".join(thread_lines))

        # 4. [Latest Follow-up] — the most recent user message
        if 0 <= latest_user_idx_in_window < len(window):
            latest = window[latest_user_idx_in_window]
            latest_content = latest.get("content", "")
            file_attachments = latest.get("file_attachments") or []
            attachment_suffix = ""
            if file_attachments:
                names = ", ".join(
                    fa.get("name", "unknown") for fa in file_attachments
                )
                attachment_suffix = f" (attached: {names})"
            result_parts.append(
                f"[Latest Follow-up]\nUser: {latest_content}{attachment_suffix}"
            )

        return "\n\n".join(result_parts)

    def _format_message(self, message: dict[str, Any]) -> str:
        """Render a single message including artifacts and file attachments."""
        author = message.get("author_name", "Unknown")
        author_type = message.get("author_type", "system")
        ts = message.get("timestamp", "")
        content = message.get("content", "")
        msg_type = message.get("type")

        # Format file attachments suffix
        file_attachments = message.get("file_attachments") or []
        attachment_suffix = ""
        if file_attachments:
            names = ", ".join(fa.get("name", "unknown") for fa in file_attachments)
            attachment_suffix = f" (attached: {names})"

        if msg_type == "step_completion":
            line = f"{author} [{author_type}] ({ts}) [Step Completion]: {content}"
            artifacts = message.get("artifacts") or []
            if artifacts:
                artifact_str = self._format_artifacts(artifacts)
                if artifact_str:
                    line += "\n" + artifact_str
            return line
        elif msg_type == "comment":
            return f"{author} [Comment]: {content}{attachment_suffix}"
        else:
            return f"{author} [{author_type}] ({ts}): {content}{attachment_suffix}"

    def _format_artifacts(self, artifacts: list[dict[str, Any]]) -> str:
        """Format artifacts for LLM context injection.

        Example output:
          Files:
          - CREATED: /output/report.pdf — Financial summary report (47 pages)
          - MODIFIED: /output/data.json — diff: +12 matched, -3 removed
        """
        if not artifacts:
            return ""
        lines = ["  Files:"]
        for a in artifacts:
            action = a.get("action", "unknown").upper()
            path = a.get("path", "unknown")
            desc = a.get("description", "")
            diff = a.get("diff", "")
            # Truncate diffs to stay within context window budget (NFR5)
            if diff and len(diff) > MAX_DIFF_LENGTH:
                diff = diff[:MAX_DIFF_LENGTH] + "... [truncated]"
            detail = desc if desc else f"diff: {diff}" if diff else ""
            line = f"  - {action}: {path}"
            if detail:
                line += f" — {detail}"
            lines.append(line)
        return "\n".join(lines)

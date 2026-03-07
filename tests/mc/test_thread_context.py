"""Comprehensive unit tests for ThreadContextBuilder.

Covers all acceptance criteria from Story 2.6:
- AC1: 20-message truncation window with omission note
- AC2: Latest user message separated into [Latest Follow-up]
- AC3: Predecessor completion messages always included
- AC4: Artifact details formatted
- AC5: Empty thread handling
- AC6: Step-aware context building
- AC7: Backward compatibility preserved
"""

from __future__ import annotations

from typing import Any

import pytest

from mc.application.execution.thread_context import ThreadContextBuilder, MAX_THREAD_MESSAGES


# ── Test helpers ──────────────────────────────────────────────────────────────


def _user_msg(
    content: str,
    timestamp: str = "2026-01-01T10:00:00Z",
) -> dict[str, Any]:
    return {
        "author_name": "User",
        "author_type": "user",
        "message_type": "user_message",
        "timestamp": timestamp,
        "content": content,
    }


def _agent_msg(
    content: str,
    author: str = "nanobot",
    timestamp: str = "2026-01-01T10:01:00Z",
) -> dict[str, Any]:
    return {
        "author_name": author,
        "author_type": "agent",
        "message_type": "work",
        "timestamp": timestamp,
        "content": content,
    }


def _step_completion_msg(
    content: str,
    step_id: str = "step-1",
    author: str = "nanobot",
    timestamp: str = "2026-01-01T10:02:00Z",
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "author_name": author,
        "author_type": "agent",
        "message_type": "work",
        "type": "step_completion",
        "step_id": step_id,
        "timestamp": timestamp,
        "content": content,
    }
    if artifacts is not None:
        msg["artifacts"] = artifacts
    return msg


# ── AC5: Empty thread handling ────────────────────────────────────────────────


class TestEmptyMessages:
    def test_empty_list_returns_empty_string(self):
        builder = ThreadContextBuilder()
        assert builder.build([]) == ""

    def test_no_user_messages_returns_empty_string_legacy(self):
        """Without predecessor IDs, no user messages → empty (backward compat)."""
        messages = [_agent_msg("Some work done.")]
        builder = ThreadContextBuilder()
        assert builder.build(messages) == ""

    def test_only_step_completion_no_predecessors_returns_empty(self):
        """Step completion without predecessor IDs + no user messages → empty."""
        messages = [_step_completion_msg("Step done.")]
        builder = ThreadContextBuilder()
        assert builder.build(messages) == ""


# ── AC7: Backward compatibility ───────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_single_user_message_included(self):
        messages = [_user_msg("Do the analysis.")]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "[Latest Follow-up]" in ctx
        assert "Do the analysis." in ctx

    def test_agent_and_user_messages(self):
        messages = [
            _agent_msg("Agent started."),
            _user_msg("Follow up with details."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "[Thread History]" in ctx
        assert "Agent started." in ctx
        assert "[Latest Follow-up]" in ctx
        assert "Follow up with details." in ctx

    def test_no_predecessor_ids_produces_same_output_as_legacy(self):
        """ThreadContextBuilder without predecessor_step_ids mirrors legacy behavior."""
        messages = [
            _agent_msg("Work done."),
            _user_msg("Please refine."),
        ]
        builder = ThreadContextBuilder()
        result_no_predecessors = builder.build(messages)
        result_explicit_none = builder.build(messages, predecessor_step_ids=None)
        result_empty_list = builder.build(messages, predecessor_step_ids=[])

        assert result_no_predecessors == result_explicit_none
        assert result_no_predecessors == result_empty_list

    def test_step_completion_message_labeled_in_legacy_path(self):
        """Legacy path still labels step_completion messages."""
        messages = [
            _step_completion_msg("Analysis complete."),
            _user_msg("Good work."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "[Step Completion]" in ctx
        assert "Analysis complete." in ctx

    def test_no_predecessor_ids_preserves_has_user_messages_guard(self):
        """Without predecessor IDs, context is empty if no user message exists."""
        messages = [
            _step_completion_msg("Step done."),
            _agent_msg("Agent work."),
        ]
        builder = ThreadContextBuilder()
        assert builder.build(messages) == ""


# ── AC1: 20-message truncation window ─────────────────────────────────────────


class TestTruncationWindow:
    def test_messages_within_window_all_included(self):
        """Up to 20 messages — all included, no omission note."""
        messages = [_user_msg(f"Message {i}") for i in range(5)]
        # Add an extra user message at the end for latest follow-up
        messages.append(_user_msg("Latest message"))
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "earlier messages omitted" not in ctx
        # First 5 are in [Thread History], last one is [Latest Follow-up]
        for i in range(5):
            assert f"Message {i}" in ctx

    def test_exactly_20_messages_no_omission(self):
        """Exactly 20 messages — no omission note."""
        messages = [_agent_msg(f"Msg {i}") for i in range(19)]
        messages.append(_user_msg("Latest"))
        assert len(messages) == 20
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "earlier messages omitted" not in ctx

    def test_21_messages_one_omitted(self):
        """21 messages → 1 earlier message omitted."""
        messages = [_agent_msg(f"Msg {i}") for i in range(20)]
        messages.append(_user_msg("Latest follow-up"))
        assert len(messages) == 21
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "(1 earlier messages omitted)" in ctx
        assert "Msg 0" not in ctx  # oldest excluded from window
        assert "Msg 1" in ctx  # within window

    def test_many_messages_truncated_with_omission_note(self):
        """30 messages → 10 earlier messages omitted."""
        messages = [_agent_msg(f"Msg {i}") for i in range(29)]
        messages.append(_user_msg("Final user question"))
        assert len(messages) == 30
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "(10 earlier messages omitted)" in ctx

    def test_custom_max_messages(self):
        """Custom max_messages=5 truncates earlier messages."""
        messages = [_agent_msg(f"Msg {i}") for i in range(9)]
        messages.append(_user_msg("Latest"))
        builder = ThreadContextBuilder()
        ctx = builder.build(messages, max_messages=5)
        assert "(5 earlier messages omitted)" in ctx


# ── AC2: Latest user message separation ───────────────────────────────────────


class TestLatestUserMessageSeparation:
    def test_latest_user_message_in_followup_section(self):
        messages = [
            _agent_msg("I started working."),
            _user_msg("Refine the analysis."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "\n[Latest Follow-up]\nUser: Refine the analysis." in ctx

    def test_latest_user_message_not_in_thread_history(self):
        messages = [
            _user_msg("First message"),
            _agent_msg("Agent reply"),
            _user_msg("Second message (latest)"),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        # Latest message in follow-up, not in thread history
        thread_section = ctx.split("[Latest Follow-up]")[0]
        assert "Second message (latest)" not in thread_section
        assert "Second message (latest)" in ctx

    def test_first_user_message_in_thread_history(self):
        """When there are 2+ user messages, the first stays in [Thread History]."""
        messages = [
            _user_msg("First user message"),
            _agent_msg("Agent reply"),
            _user_msg("Latest user follow-up"),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        thread_section = ctx.split("[Latest Follow-up]")[0]
        assert "First user message" in thread_section

    def test_only_one_user_message_in_followup_not_history(self):
        """Single user message goes only to [Latest Follow-up]."""
        messages = [
            _agent_msg("Work done."),
            _user_msg("The only user message."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        thread_section = ctx.split("[Latest Follow-up]")[0]
        assert "The only user message." not in thread_section
        assert "[Latest Follow-up]\nUser: The only user message." in ctx


# ── AC3: Predecessor completion messages always included ──────────────────────


class TestPredecessorMessages:
    def test_predecessor_in_window_at_natural_position(self):
        """Predecessor within window appears naturally in [Thread History]."""
        predecessor_msg = _step_completion_msg(
            "Step 1 complete.", step_id="step-1", timestamp="2026-01-01T10:00:00Z"
        )
        messages = [
            predecessor_msg,
            _user_msg("Great, continue."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-1"])
        # Predecessor is within window — no [Predecessor Context] preamble
        assert "[Predecessor Context]" not in ctx
        assert "Step 1 complete." in ctx

    def test_predecessor_outside_window_injected_as_preamble(self):
        """Predecessor outside 20-message window injected as [Predecessor Context]."""
        predecessor_msg = _step_completion_msg(
            "Step 1 complete.", step_id="step-1", timestamp="2026-01-01T09:00:00Z"
        )
        # Fill up 20 more messages after the predecessor
        later_messages = [_agent_msg(f"Later msg {i}") for i in range(19)]
        later_messages.append(_user_msg("Final user question"))
        messages = [predecessor_msg] + later_messages
        assert len(messages) == 21  # predecessor is in position 0, outside window

        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-1"])

        # Predecessor should appear in [Predecessor Context]
        assert "[Predecessor Context]" in ctx
        assert "Step 1 complete." in ctx

    def test_predecessor_outside_window_still_has_omission_note(self):
        """When truncated, omission note accounts for predecessors shown in preamble.

        The predecessor message is explicitly shown in [Predecessor Context],
        so only truly hidden messages count as "omitted".
        """
        predecessor_msg = _step_completion_msg(
            "Step 1 done.", step_id="step-1", timestamp="2026-01-01T09:00:00Z"
        )
        later_messages = [_agent_msg(f"Msg {i}") for i in range(19)]
        later_messages.append(_user_msg("Follow-up"))
        messages = [predecessor_msg] + later_messages
        assert len(messages) == 21

        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-1"])

        # Only 1 message omitted from window, but it's the predecessor shown
        # in preamble, so effective omitted = 0 — no omission note.
        assert "earlier messages omitted" not in ctx
        assert "[Predecessor Context]" in ctx

    def test_omission_note_with_predecessors_and_non_predecessor_omissions(self):
        """Omission note correctly counts only non-predecessor omitted messages."""
        predecessor_msg = _step_completion_msg(
            "Step 1 done.", step_id="step-1", timestamp="2026-01-01T08:00:00Z"
        )
        extra_early_msg = _agent_msg("Very early work", timestamp="2026-01-01T08:30:00Z")
        later_messages = [_agent_msg(f"Msg {i}") for i in range(19)]
        later_messages.append(_user_msg("Follow-up"))
        messages = [predecessor_msg, extra_early_msg] + later_messages
        assert len(messages) == 22

        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-1"])

        # 2 messages omitted from window: predecessor + extra_early.
        # Predecessor is shown in preamble, so effective omitted = 1.
        assert "(1 earlier messages omitted)" in ctx
        assert "[Predecessor Context]" in ctx

    def test_multiple_predecessors_all_included(self):
        """All predecessor completion messages included even outside window."""
        pred1 = _step_completion_msg(
            "Step 1 done.", step_id="step-1", timestamp="2026-01-01T09:00:00Z"
        )
        pred2 = _step_completion_msg(
            "Step 2 done.", step_id="step-2", timestamp="2026-01-01T09:01:00Z"
        )
        later_messages = [_agent_msg(f"Msg {i}") for i in range(19)]
        later_messages.append(_user_msg("Continue with step 3"))
        messages = [pred1, pred2] + later_messages
        assert len(messages) == 22

        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-1", "step-2"])

        assert "Step 1 done." in ctx
        assert "Step 2 done." in ctx

    def test_predecessor_step_id_only_matches_step_completion_type(self):
        """Only messages with type='step_completion' are treated as predecessors."""
        non_completion = _agent_msg("Regular message from step 1 agent")
        # Give it a step_id but no type="step_completion"
        non_completion["step_id"] = "step-1"

        later_messages = [_agent_msg(f"Msg {i}") for i in range(19)]
        later_messages.append(_user_msg("Follow-up"))
        messages = [non_completion] + later_messages
        assert len(messages) == 21

        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-1"])

        # Non-completion message with step_id should NOT be in [Predecessor Context]
        assert "[Predecessor Context]" not in ctx

    def test_with_predecessors_no_user_messages_still_builds_context(self):
        """Step-aware mode builds context even with no user messages."""
        pred_msg = _step_completion_msg(
            "Predecessor complete.", step_id="step-1"
        )
        messages = [pred_msg]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-1"])
        # Should have content (predecessor context) even without user messages
        assert ctx != ""
        assert "Predecessor complete." in ctx

    def test_predecessor_in_window_no_preamble_section(self):
        """When predecessor is inside the window, no [Predecessor Context] preamble."""
        messages = [
            _agent_msg("Some other message"),
            _step_completion_msg("Within-window predecessor.", step_id="step-5"),
            _user_msg("Please review"),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-5"])
        assert "[Predecessor Context]" not in ctx
        assert "Within-window predecessor." in ctx


# ── AC4: Artifact formatting ──────────────────────────────────────────────────


class TestArtifactFormatting:
    def test_created_artifact_formatted(self):
        messages = [
            _step_completion_msg(
                "Generated report.",
                step_id="step-1",
                artifacts=[{
                    "path": "output/report.pdf",
                    "action": "created",
                    "description": "PDF, 245 KB",
                }],
            ),
            _user_msg("Review it."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "CREATED: output/report.pdf" in ctx
        assert "PDF, 245 KB" in ctx

    def test_modified_artifact_with_diff(self):
        messages = [
            _step_completion_msg(
                "Updated data.",
                step_id="step-1",
                artifacts=[{
                    "path": "output/data.json",
                    "action": "modified",
                    "diff": "File updated (12 KB)",
                }],
            ),
            _user_msg("Thanks."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "MODIFIED: output/data.json" in ctx
        assert "diff: File updated (12 KB)" in ctx

    def test_artifact_without_description_or_diff(self):
        messages = [
            _step_completion_msg(
                "Processed file.",
                step_id="step-1",
                artifacts=[{"path": "output/x.bin", "action": "created"}],
            ),
            _user_msg("Ok."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "CREATED: output/x.bin" in ctx
        # No " — " separator when no detail
        assert "CREATED: output/x.bin —" not in ctx

    def test_multiple_artifacts_all_rendered(self):
        messages = [
            _step_completion_msg(
                "Multiple files.",
                step_id="step-1",
                artifacts=[
                    {"path": "output/a.pdf", "action": "created", "description": "PDF, 10 KB"},
                    {"path": "output/b.json", "action": "modified", "diff": "+2 KB"},
                ],
            ),
            _user_msg("Review."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "CREATED: output/a.pdf" in ctx
        assert "PDF, 10 KB" in ctx
        assert "MODIFIED: output/b.json" in ctx
        assert "diff: +2 KB" in ctx

    def test_empty_artifacts_list_no_files_section(self):
        messages = [
            _step_completion_msg("Done.", step_id="step-1", artifacts=[]),
            _user_msg("Ok."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "[Step Completion]" in ctx
        assert "Files:" not in ctx

    def test_diff_truncated_at_2000_chars(self):
        long_diff = "x" * 3000
        messages = [
            _step_completion_msg(
                "Big diff.",
                step_id="step-1",
                artifacts=[{"path": "output/big.patch", "action": "modified", "diff": long_diff}],
            ),
            _user_msg("Review."),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages)
        assert "[truncated]" in ctx
        # The diff in context should be shorter than the original
        assert long_diff not in ctx

    def test_predecessor_artifacts_included_in_preamble(self):
        """Predecessor outside window with artifacts — artifacts shown in preamble."""
        pred = _step_completion_msg(
            "Step 1 done.",
            step_id="step-1",
            artifacts=[{"path": "output/step1_report.pdf", "action": "created", "description": "PDF, 50 KB"}],
        )
        later_messages = [_agent_msg(f"Msg {i}") for i in range(19)]
        later_messages.append(_user_msg("Continue"))
        messages = [pred] + later_messages

        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-1"])

        assert "[Predecessor Context]" in ctx
        assert "step1_report.pdf" in ctx
        assert "PDF, 50 KB" in ctx


# ── AC6: Step-aware context with step description ─────────────────────────────


class TestStepAwareContext:
    def test_predecessor_step_ids_triggers_step_aware_mode(self):
        """Providing predecessor_step_ids switches to step-aware mode."""
        messages = [
            _step_completion_msg("Pred done.", step_id="step-1"),
        ]
        builder = ThreadContextBuilder()
        ctx = builder.build(messages, predecessor_step_ids=["step-1"])
        # Step-aware mode: context built even without user messages
        assert ctx != ""

    def test_non_matching_step_id_not_treated_as_predecessor(self):
        """Messages with non-matching step_ids are not treated as predecessors."""
        messages = [
            _step_completion_msg("Step X done.", step_id="step-X"),
        ]
        builder = ThreadContextBuilder()
        # step-Y is not in the message's step_id
        ctx = builder.build(messages, predecessor_step_ids=["step-Y"])
        # No predecessors found, no user messages → empty
        assert ctx == ""

    def test_empty_predecessor_ids_list_same_as_none(self):
        """Empty predecessor IDs list falls back to legacy behavior."""
        messages = [_step_completion_msg("Work done.")]
        builder = ThreadContextBuilder()
        ctx_none = builder.build(messages, predecessor_step_ids=None)
        ctx_empty = builder.build(messages, predecessor_step_ids=[])
        assert ctx_none == ctx_empty == ""


# ── _format_artifacts unit tests ─────────────────────────────────────────────


class TestFormatArtifacts:
    def test_empty_list_returns_empty_string(self):
        builder = ThreadContextBuilder()
        assert builder._format_artifacts([]) == ""

    def test_single_created_artifact(self):
        builder = ThreadContextBuilder()
        result = builder._format_artifacts([
            {"path": "output/report.pdf", "action": "created", "description": "PDF, 47 pages"}
        ])
        assert "CREATED: output/report.pdf" in result
        assert "PDF, 47 pages" in result
        assert "Files:" in result

    def test_description_takes_precedence_over_diff(self):
        """When both description and diff present, description is shown."""
        builder = ThreadContextBuilder()
        result = builder._format_artifacts([{
            "path": "output/x.txt",
            "action": "modified",
            "description": "Updated file",
            "diff": "+5 lines",
        }])
        assert "Updated file" in result
        # diff should not appear when description is present
        assert "diff:" not in result

    def test_diff_shown_when_no_description(self):
        builder = ThreadContextBuilder()
        result = builder._format_artifacts([{
            "path": "output/x.txt",
            "action": "modified",
            "diff": "+5 lines",
        }])
        assert "diff: +5 lines" in result

    def test_no_description_or_diff_no_separator(self):
        builder = ThreadContextBuilder()
        result = builder._format_artifacts([{"path": "output/x.bin", "action": "created"}])
        assert "CREATED: output/x.bin" in result
        assert " — " not in result

    def test_diff_truncated(self):
        builder = ThreadContextBuilder()
        long_diff = "y" * 2500
        result = builder._format_artifacts([{"path": "f", "action": "modified", "diff": long_diff}])
        assert "[truncated]" in result
        assert len(result) < len(long_diff) + 200  # sanity check


# ── Integration: shim test ─────────────────────────────────────────────────────


class TestExecutorShim:
    def test_shim_delegates_to_thread_context_builder(self):
        """_build_thread_context shim in executor delegates to ThreadContextBuilder."""
        from mc.executor import _build_thread_context

        messages = [
            _agent_msg("Agent started."),
            _user_msg("Please do the analysis."),
        ]
        result = _build_thread_context(messages)
        # Should match ThreadContextBuilder output
        expected = ThreadContextBuilder().build(messages)
        assert result == expected

    def test_shim_empty_returns_empty(self):
        from mc.executor import _build_thread_context

        assert _build_thread_context([]) == ""

    def test_shim_no_user_messages_returns_empty(self):
        from mc.executor import _build_thread_context

        messages = [_agent_msg("Some work.")]
        assert _build_thread_context(messages) == ""

    def test_shim_step_completion_with_artifacts(self):
        """Shim correctly handles step_completion messages with artifacts."""
        from mc.executor import _build_thread_context

        messages = [
            _step_completion_msg(
                "Analysis done.",
                artifacts=[{"path": "output/report.pdf", "action": "created", "description": "PDF, 245 KB"}],
            ),
            _user_msg("Good."),
        ]
        ctx = _build_thread_context(messages)
        # Old tests used "Artifacts:" but new builder uses "Files:"
        # Verify artifact content is still present
        assert "report.pdf" in ctx
        assert "PDF, 245 KB" in ctx


# ── File attachments ──────────────────────────────────────────────────────────


def test_file_attachments_in_user_message():
    """File attachments are rendered as (attached: ...) suffix."""
    builder = ThreadContextBuilder()
    messages = [
        {
            "author_name": "User",
            "author_type": "user",
            "message_type": "user_message",
            "type": "user_message",
            "content": "Analyze this report",
            "timestamp": "2026-03-05T10:00:00Z",
            "file_attachments": [
                {"name": "report.pdf", "type": "application/pdf", "size": 1024},
                {"name": "data.csv", "type": "text/csv", "size": 512},
            ],
        },
    ]
    result = builder.build(messages)
    assert "(attached: report.pdf, data.csv)" in result
    assert "Analyze this report" in result

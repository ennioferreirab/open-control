from __future__ import annotations

from mc.contexts.integrations.status_mapping import (
    DEFAULT_INBOUND_STATUS_MAP,
    DEFAULT_OUTBOUND_STATUS_MAP,
    resolve_status_inbound,
    resolve_status_outbound,
)
from mc.types import TaskStatus


class TestDefaultInboundStatusMap:
    def test_triage_maps_to_inbox(self) -> None:
        assert resolve_status_inbound("triage") == "inbox"

    def test_backlog_maps_to_inbox(self) -> None:
        assert resolve_status_inbound("backlog") == "inbox"

    def test_unstarted_maps_to_inbox(self) -> None:
        assert resolve_status_inbound("unstarted") == "inbox"

    def test_started_maps_to_in_progress(self) -> None:
        assert resolve_status_inbound("started") == "in_progress"

    def test_completed_maps_to_done(self) -> None:
        assert resolve_status_inbound("completed") == "done"

    def test_canceled_maps_to_done(self) -> None:
        assert resolve_status_inbound("canceled") == "done"

    def test_all_default_inbound_keys_covered(self) -> None:
        # Ensure this test stays in sync with the map definition
        expected_keys = {"triage", "backlog", "unstarted", "started", "completed", "canceled"}
        assert set(DEFAULT_INBOUND_STATUS_MAP.keys()) == expected_keys


class TestDefaultOutboundStatusMap:
    def test_inbox_maps_to_unstarted(self) -> None:
        assert resolve_status_outbound("inbox") == "unstarted"

    def test_assigned_maps_to_started(self) -> None:
        assert resolve_status_outbound("assigned") == "started"

    def test_in_progress_maps_to_started(self) -> None:
        assert resolve_status_outbound("in_progress") == "started"

    def test_review_maps_to_started(self) -> None:
        assert resolve_status_outbound("review") == "started"

    def test_done_maps_to_completed(self) -> None:
        assert resolve_status_outbound("done") == "completed"

    def test_deleted_maps_to_canceled(self) -> None:
        assert resolve_status_outbound("deleted") == "canceled"

    def test_crashed_maps_to_started(self) -> None:
        assert resolve_status_outbound("crashed") == "started"

    def test_retrying_maps_to_started(self) -> None:
        assert resolve_status_outbound("retrying") == "started"

    def test_ready_maps_to_backlog(self) -> None:
        assert resolve_status_outbound("ready") == "backlog"

    def test_failed_maps_to_canceled(self) -> None:
        assert resolve_status_outbound("failed") == "canceled"

    def test_all_default_outbound_keys_covered(self) -> None:
        expected_keys = {
            "inbox",
            "assigned",
            "in_progress",
            "review",
            "done",
            "deleted",
            "crashed",
            "retrying",
            "ready",
            "failed",
        }
        assert set(DEFAULT_OUTBOUND_STATUS_MAP.keys()) == expected_keys


class TestUnmappedStatuses:
    def test_unknown_inbound_returns_none(self) -> None:
        assert resolve_status_inbound("unknown_state") is None

    def test_empty_string_inbound_returns_none(self) -> None:
        assert resolve_status_inbound("") is None

    def test_unknown_outbound_returns_none(self) -> None:
        assert resolve_status_outbound("unknown_state") is None

    def test_empty_string_outbound_returns_none(self) -> None:
        assert resolve_status_outbound("") is None


class TestCustomMappingOverride:
    def test_custom_inbound_overrides_default(self) -> None:
        custom = {"custom_state": "in_progress"}
        assert resolve_status_inbound("custom_state", custom_mapping=custom) == "in_progress"

    def test_custom_inbound_does_not_fall_through_to_default(self) -> None:
        # When a custom mapping is provided, default map entries are ignored
        custom = {"custom_state": "in_progress"}
        assert resolve_status_inbound("triage", custom_mapping=custom) is None

    def test_custom_outbound_overrides_default(self) -> None:
        custom = {"my_status": "triaged"}
        assert resolve_status_outbound("my_status", custom_mapping=custom) == "triaged"

    def test_custom_outbound_does_not_fall_through_to_default(self) -> None:
        custom = {"my_status": "triaged"}
        assert resolve_status_outbound("inbox", custom_mapping=custom) is None


class TestEmptyCustomMapping:
    def test_empty_inbound_custom_mapping_returns_none(self) -> None:
        # Explicit empty dict means "no mappings" — does NOT fall back to defaults
        assert resolve_status_inbound("triage", custom_mapping={}) is None

    def test_empty_outbound_custom_mapping_returns_none(self) -> None:
        # Explicit empty dict means "no mappings" — does NOT fall back to defaults
        assert resolve_status_outbound("done", custom_mapping={}) is None

    def test_none_custom_mapping_falls_back_to_default(self) -> None:
        # None (the default) correctly falls back to DEFAULT_*_STATUS_MAP
        assert resolve_status_inbound("triage", custom_mapping=None) == "inbox"
        assert resolve_status_outbound("done", custom_mapping=None) == "completed"


class TestOutboundMapCoversAllTaskStatuses:
    def test_all_task_statuses_have_outbound_mapping(self) -> None:
        """Every TaskStatus value must be present as a key in the default outbound map."""
        missing = [
            status.value for status in TaskStatus if status.value not in DEFAULT_OUTBOUND_STATUS_MAP
        ]
        assert missing == [], (
            f"TaskStatus values missing from DEFAULT_OUTBOUND_STATUS_MAP: {missing}"
        )

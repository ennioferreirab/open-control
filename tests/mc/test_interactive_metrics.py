from mc.contexts.interactive.metrics import (
    increment_interactive_metric,
    reset_interactive_metrics,
    snapshot_interactive_metrics,
)


def test_interactive_metrics_track_named_counters() -> None:
    reset_interactive_metrics()

    increment_interactive_metric("interactive_startup_success_total")
    increment_interactive_metric("interactive_startup_success_total")
    increment_interactive_metric("interactive_session_crash_total")

    assert snapshot_interactive_metrics() == {
        "interactive_startup_success_total": 2,
        "interactive_session_crash_total": 1,
    }

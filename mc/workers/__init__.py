"""Workers package — domain-specific handlers extracted from the orchestrator.

Each worker handles one concern (inbox, planning, review, kickoff/resume)
and receives dependencies via constructor injection. The orchestrator
creates workers and routes subscription events to them.

Imports are lazy to avoid circular dependencies with mc.orchestrator.
"""


def __getattr__(name: str) -> object:
    """Lazy module attribute access to avoid circular imports."""
    if name == "InboxWorker":
        from mc.workers.inbox import InboxWorker
        return InboxWorker
    if name == "PlanningWorker":
        from mc.workers.planning import PlanningWorker
        return PlanningWorker
    if name == "ReviewWorker":
        from mc.workers.review import ReviewWorker
        return ReviewWorker
    if name == "KickoffResumeWorker":
        from mc.workers.kickoff import KickoffResumeWorker
        return KickoffResumeWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "InboxWorker",
    "KickoffResumeWorker",
    "PlanningWorker",
    "ReviewWorker",
]

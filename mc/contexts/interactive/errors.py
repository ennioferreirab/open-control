"""SHARED: Interactive session error types."""

from __future__ import annotations


class InteractiveSessionError(RuntimeError):
    """Base error for interactive session failures."""


class InteractiveSessionBinaryMissingError(InteractiveSessionError):
    """Raised when a required interactive CLI binary is not available."""


class InteractiveSessionBootstrapError(InteractiveSessionError):
    """Raised when workspace/bootstrap preparation fails."""


class InteractiveSessionStartupError(InteractiveSessionError):
    """Raised when the reconnectable terminal session cannot start."""


class InteractiveSessionAttachError(InteractiveSessionError):
    """Raised when attaching a PTY client to a live interactive session fails."""

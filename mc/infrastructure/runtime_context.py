"""
RuntimeContext — lightweight container for runtime dependencies.

Modules receive this via constructor injection or function parameters
instead of importing gateway directly.  Holds references to bridge,
config paths, and service references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.infrastructure.runtime_home import get_agents_dir

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge


@dataclass
class RuntimeContext:
    """Lightweight container holding runtime dependencies.

    Instead of importing from mc.gateway, modules accept a RuntimeContext
    (or its individual fields) via dependency injection.

    Attributes:
        bridge: ConvexBridge instance for Convex communication.
        agents_dir: Path to the agents directory (default: configured runtime home / agents).
        admin_key: The Convex admin key (resolved at startup).
        admin_url: The Convex deployment URL (resolved at startup).
        services: Optional dict for holding arbitrary service references.
    """

    bridge: ConvexBridge
    agents_dir: Path = field(default_factory=get_agents_dir)
    admin_key: str = ""
    admin_url: str = ""
    services: dict[str, Any] = field(default_factory=dict)

"""
Infrastructure package — config, env resolution, path utilities, and agent bootstrap.

This package holds everything that was previously in mc.gateway but is NOT
bootstrap/wiring/lifecycle logic.  Internal MC modules import from here
instead of from mc.gateway (architectural rule: services cannot import gateway).
"""

from mc.infrastructure.config import (
    AGENTS_DIR,
    _config_default_model,
    _parse_utc_timestamp,
    _read_file_or_none,
    _read_session_data,
    _resolve_admin_key,
    _resolve_convex_url,
    filter_agent_fields,
)

__all__ = [
    "AGENTS_DIR",
    "_config_default_model",
    "_parse_utc_timestamp",
    "_read_file_or_none",
    "_read_session_data",
    "_resolve_admin_key",
    "_resolve_convex_url",
    "filter_agent_fields",
]

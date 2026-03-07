"""Tests verifying process_monitor.py decomposition (Story 20.5).

Ensures that all functions previously in mc/process_monitor.py are accessible
from their canonical modules (mc.infrastructure.config, mc.infrastructure.agent_bootstrap,
mc.contexts.execution.crash_recovery, mc.services.plan_negotiation) and via mc.gateway re-exports.
"""

from __future__ import annotations

import pytest


class TestConfigFunctionsAccessible:
    """AC1: Config/defaults extracted to mc.infrastructure.config."""

    def test_config_default_model_importable(self) -> None:
        from mc.infrastructure.config import _config_default_model
        assert callable(_config_default_model)

    def test_resolve_convex_url_importable(self) -> None:
        from mc.infrastructure.config import _resolve_convex_url
        assert callable(_resolve_convex_url)

    def test_resolve_admin_key_importable(self) -> None:
        from mc.infrastructure.config import _resolve_admin_key
        assert callable(_resolve_admin_key)

    def test_filter_agent_fields_importable(self) -> None:
        from mc.infrastructure.config import filter_agent_fields
        assert callable(filter_agent_fields)

    def test_parse_utc_timestamp_importable(self) -> None:
        from mc.infrastructure.config import _parse_utc_timestamp
        assert callable(_parse_utc_timestamp)

    def test_read_file_or_none_importable(self) -> None:
        from mc.infrastructure.config import _read_file_or_none
        assert callable(_read_file_or_none)

    def test_read_session_data_importable(self) -> None:
        from mc.infrastructure.config import _read_session_data
        assert callable(_read_session_data)


class TestSyncUtilitiesAccessible:
    """AC2: Sync utilities extracted to mc.infrastructure.agent_bootstrap."""

    def test_sync_model_tiers_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import _sync_model_tiers
        assert callable(_sync_model_tiers)

    def test_sync_embedding_model_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import _sync_embedding_model
        assert callable(_sync_embedding_model)

    def test_distribute_builtin_skills_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import _distribute_builtin_skills
        assert callable(_distribute_builtin_skills)

    def test_sync_skills_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import sync_skills
        assert callable(sync_skills)

    def test_sync_agent_registry_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import sync_agent_registry
        assert callable(sync_agent_registry)

    def test_sync_nanobot_default_model_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import sync_nanobot_default_model
        assert callable(sync_nanobot_default_model)

    def test_ensure_low_agent_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import ensure_low_agent
        assert callable(ensure_low_agent)

    def test_ensure_nanobot_agent_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import ensure_nanobot_agent
        assert callable(ensure_nanobot_agent)

    def test_fetch_bot_identity_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import _fetch_bot_identity
        assert callable(_fetch_bot_identity)


class TestCleanupLogicAccessible:
    """AC3: Cleanup logic extracted to mc.infrastructure.agent_bootstrap."""

    def test_cleanup_deleted_agents_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import _cleanup_deleted_agents
        assert callable(_cleanup_deleted_agents)

    def test_restore_archived_files_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import _restore_archived_files
        assert callable(_restore_archived_files)

    def test_write_back_convex_agents_importable(self) -> None:
        from mc.infrastructure.agent_bootstrap import _write_back_convex_agents
        assert callable(_write_back_convex_agents)


class TestCrashHandlerAccessible:
    """AgentGateway crash handler extracted to mc.contexts.execution.crash_recovery."""

    def test_agent_gateway_importable(self) -> None:
        from mc.contexts.execution.crash_recovery import AgentGateway
        assert AgentGateway is not None

    def test_max_auto_retries_importable(self) -> None:
        from mc.contexts.execution.crash_recovery import MAX_AUTO_RETRIES
        assert MAX_AUTO_RETRIES == 1


class TestPlanNegotiationAccessible:
    """Plan negotiation manager extracted to mc.services.plan_negotiation."""

    def test_plan_negotiation_supervisor_importable(self) -> None:
        from mc.services.plan_negotiation import PlanNegotiationSupervisor
        assert PlanNegotiationSupervisor is not None


class TestGatewayReExports:
    """Backward compat: mc.gateway re-exports all decomposed symbols."""

    def test_gateway_reexports_config_functions(self) -> None:
        from mc.gateway import (
            AGENTS_DIR,
            _config_default_model,
            _parse_utc_timestamp,
            _read_file_or_none,
            _read_session_data,
            _resolve_admin_key,
            _resolve_convex_url,
            filter_agent_fields,
        )
        assert AGENTS_DIR is not None
        assert callable(_config_default_model)
        assert callable(_resolve_convex_url)
        assert callable(_resolve_admin_key)
        assert callable(filter_agent_fields)
        assert callable(_parse_utc_timestamp)
        assert callable(_read_file_or_none)
        assert callable(_read_session_data)

    def test_gateway_reexports_bootstrap_functions(self) -> None:
        from mc.gateway import (
            _NANOBOT_AGENT_CONFIG,
            NANOBOT_AGENT_NAME,
            _cleanup_deleted_agents,
            _distribute_builtin_skills,
            _fetch_bot_identity,
            _restore_archived_files,
            _sync_embedding_model,
            _sync_model_tiers,
            _write_back_convex_agents,
            ensure_low_agent,
            ensure_nanobot_agent,
            sync_agent_registry,
            sync_nanobot_default_model,
            sync_skills,
        )
        assert NANOBOT_AGENT_NAME is not None
        assert _NANOBOT_AGENT_CONFIG is not None
        assert callable(ensure_low_agent)
        assert callable(ensure_nanobot_agent)
        assert callable(sync_agent_registry)
        assert callable(sync_nanobot_default_model)
        assert callable(sync_skills)
        assert callable(_sync_model_tiers)
        assert callable(_sync_embedding_model)
        assert callable(_distribute_builtin_skills)
        assert callable(_cleanup_deleted_agents)
        assert callable(_restore_archived_files)
        assert callable(_write_back_convex_agents)
        assert callable(_fetch_bot_identity)

    def test_gateway_reexports_crash_handler(self) -> None:
        from mc.gateway import MAX_AUTO_RETRIES, AgentGateway
        assert AgentGateway is not None
        assert MAX_AUTO_RETRIES == 1


class TestDeadCodeRemoved:
    """AC4: process_monitor.py and agent_sync.py (top-level) are removed."""

    def test_process_monitor_not_importable(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            import mc.process_monitor  # noqa: F401

    def test_agent_sync_top_level_not_importable(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            import mc.agent_sync  # noqa: F401


class TestAgentSyncService:
    """AC2 supplement: AgentSyncService accessible from mc.services.agent_sync."""

    def test_agent_sync_service_importable(self) -> None:
        from mc.services.agent_sync import AgentSyncService
        assert AgentSyncService is not None

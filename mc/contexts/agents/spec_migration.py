"""Agent Spec V2 migration module.

Migrates the existing agent catalog (local config.yaml + SOUL.md files) into
Agent Spec V2 records in Convex, then publishes runtime projections.

Usage:
    python -m mc.contexts.agents.spec_migration [--agents-dir PATH] [--dry-run]

This module is safe to rerun: it checks whether a spec already exists for each
agent before creating a new one.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from mc.infrastructure.agents.yaml_validator import validate_agent_file
from mc.infrastructure.runtime_home import get_agents_dir

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class MigrationResult(TypedDict):
    """Summary returned by migrate_all."""

    migrated: list[str]
    skipped: list[str]
    errors: dict[str, str]


def build_spec_payload_from_yaml(config_path: Path) -> dict[str, Any] | None:
    """Build an Agent Spec V2 payload dict from a local config.yaml file.

    Reuses the existing YAML validator to parse and validate the agent config.
    Reads SOUL.md from the same directory if present.

    Args:
        config_path: Path to the agent's config.yaml file.

    Returns:
        A dict suitable for passing to bridge.create_agent_spec(), or None
        if the YAML file is invalid.
    """
    result = validate_agent_file(config_path)

    if isinstance(result, list):
        # Validation errors
        logger.warning(
            "Invalid agent YAML at %s: %s",
            config_path,
            "; ".join(result),
        )
        return None

    agent_data = result

    payload: dict[str, Any] = {
        "name": agent_data.name,
        "role": agent_data.role,
        "prompt": agent_data.prompt,
        "skills": agent_data.skills or [],
    }

    if agent_data.display_name and agent_data.display_name != agent_data.name:
        payload["display_name"] = agent_data.display_name

    if agent_data.model:
        payload["model"] = agent_data.model

    if agent_data.soul:
        payload["soul"] = agent_data.soul

    return payload


def migrate_agent(
    config_path: Path,
    bridge: ConvexBridge,
    dry_run: bool = False,
    *,
    _prebuilt_payload: dict[str, Any] | None = None,
    _skip_idempotency_check: bool = False,
) -> str | None:
    """Migrate a single agent from config.yaml into an Agent Spec V2 record.

    This function is idempotent: if a spec already exists for the agent, it
    returns the existing spec's ID without creating a duplicate.

    Args:
        config_path: Path to the agent's config.yaml file.
        bridge: ConvexBridge instance for Convex communication.
        dry_run: If True, build the payload but do not write to Convex.
        _prebuilt_payload: Optional pre-validated payload dict.  When provided
            the YAML build step is skipped (avoids double-validation).
        _skip_idempotency_check: When True the idempotency check is skipped
            because the caller (migrate_all) has already performed it.

    Returns:
        The spec document ID (existing or newly created), or None if the YAML
        is invalid or an error occurs.
    """
    if _prebuilt_payload is not None:
        payload = _prebuilt_payload
    else:
        payload = build_spec_payload_from_yaml(config_path)
        if payload is None:
            return None

    agent_name = payload["name"]

    if dry_run:
        logger.info("[migration] DRY RUN: would migrate agent '%s'", agent_name)
        return f"dry-run:{agent_name}"

    # Idempotency check: skip if a spec already exists (skip when caller did it)
    if not _skip_idempotency_check:
        existing = bridge.get_agent_spec_by_name(agent_name)
        if existing is not None:
            existing_id = existing.get("_id") or existing.get("id")
            logger.info(
                "[migration] Agent '%s' already has a spec (%s) — skipping",
                agent_name,
                existing_id,
            )
            return existing_id

    # Create the spec
    try:
        spec_id = bridge.create_agent_spec(**payload)
        logger.info("[migration] Created spec for agent '%s' → %s", agent_name, spec_id)
    except Exception:
        logger.exception("[migration] Failed to create spec for agent '%s'", agent_name)
        return None

    if spec_id is None:
        logger.warning("[migration] create_agent_spec returned None for '%s'", agent_name)
        return None

    # Publish to generate the runtime projection
    try:
        bridge.publish_agent_spec(spec_id)
        logger.info("[migration] Published spec %s for agent '%s'", spec_id, agent_name)
    except Exception:
        logger.exception(
            "[migration] Failed to publish spec %s for agent '%s'",
            spec_id,
            agent_name,
        )
        # Return spec_id anyway — the spec was created, just not published
        return spec_id

    return spec_id


def migrate_all(
    agents_dir: Path,
    bridge: ConvexBridge,
    dry_run: bool = False,
) -> MigrationResult:
    """Migrate all agents in a directory into Agent Spec V2 records.

    Iterates over subdirectories in agents_dir, validates each config.yaml,
    and calls migrate_agent() for each valid agent.

    Args:
        agents_dir: Path to the local agents directory (e.g. ~/.nanobot/agents).
        bridge: ConvexBridge instance for Convex communication.
        dry_run: If True, report planned changes without writing to Convex.

    Returns:
        Summary dict with keys:
            - "migrated": list of agent names successfully migrated
            - "skipped": list of agent names that already had a spec
            - "errors": dict of agent_name -> error description
    """
    migrated: list[str] = []
    skipped: list[str] = []
    errors: dict[str, str] = {}

    if not agents_dir.is_dir():
        logger.warning("[migration] Agents directory not found: %s", agents_dir)
        return {"migrated": migrated, "skipped": skipped, "errors": errors}

    for child in sorted(agents_dir.iterdir()):
        config_file = child / "config.yaml"
        if not (child.is_dir() and config_file.is_file()):
            continue

        agent_name = child.name

        # Check for validation errors first
        payload = build_spec_payload_from_yaml(config_file)
        if payload is None:
            errors[agent_name] = "Invalid config.yaml — see logs for details"
            continue

        # Check idempotency (even in dry_run mode for correct reporting)
        existing = None
        if not dry_run:
            try:
                existing = bridge.get_agent_spec_by_name(agent_name)
            except Exception:
                logger.warning(
                    "[migration] Could not check existing spec for '%s'",
                    agent_name,
                )
        else:
            try:
                existing = bridge.get_agent_spec_by_name(agent_name)
            except Exception:
                logger.warning(
                    "[spec_migration] Failed to lookup spec for agent '%s'",
                    agent_name,
                    exc_info=True,
                )

        if existing is not None:
            logger.info("[migration] Skipping '%s' — spec already exists", agent_name)
            skipped.append(agent_name)
            continue

        # Migrate the agent — pass the pre-built payload and skip re-check
        spec_id = migrate_agent(
            config_path=config_file,
            bridge=bridge,
            dry_run=dry_run,
            _prebuilt_payload=payload,
            _skip_idempotency_check=True,
        )
        if spec_id is not None:
            migrated.append(agent_name)
        else:
            errors[agent_name] = "Migration failed — see logs for details"

    return {"migrated": migrated, "skipped": skipped, "errors": errors}


def main() -> None:
    """CLI entrypoint for running the migration from the command line.

    Usage:
        python -m mc.contexts.agents.spec_migration [--agents-dir PATH] [--dry-run]
    """
    parser = argparse.ArgumentParser(
        description="Migrate existing agents to Agent Spec V2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m mc.contexts.agents.spec_migration
  python -m mc.contexts.agents.spec_migration --dry-run
  python -m mc.contexts.agents.spec_migration --agents-dir /custom/agents/path
        """,
    )
    parser.add_argument(
        "--agents-dir",
        type=Path,
        default=get_agents_dir(),
        help="Path to local agents directory (default: ~/.nanobot/agents)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned changes without writing to Convex",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    import os

    deployment_url = os.environ.get("CONVEX_URL", "")
    if not deployment_url and not args.dry_run:
        print(
            "ERROR: CONVEX_URL environment variable is required for non-dry-run migration.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.dry_run and not deployment_url:
        print("[DRY RUN] CONVEX_URL not set — performing local-only dry run")
        # In dry-run mode without a bridge, just list agents that would be migrated
        agents_dir: Path = args.agents_dir
        if not agents_dir.is_dir():
            print(f"Agents directory not found: {agents_dir}")
            sys.exit(0)
        planned = []
        for child in sorted(agents_dir.iterdir()):
            config_file = child / "config.yaml"
            if child.is_dir() and config_file.is_file():
                payload = build_spec_payload_from_yaml(config_file)
                if payload is not None:
                    planned.append(payload["name"])
                    print(f"  [DRY RUN] Would migrate: {payload['name']} ({payload['role']})")
        print(f"\nTotal: {len(planned)} agent(s) would be migrated")
        return

    from mc.bridge import ConvexBridge

    admin_key = os.environ.get("CONVEX_ADMIN_KEY")
    bridge = ConvexBridge(deployment_url, admin_key)

    try:
        results = migrate_all(
            agents_dir=args.agents_dir,
            bridge=bridge,
            dry_run=args.dry_run,
        )
    finally:
        bridge.close()

    print(f"\nMigration {'(DRY RUN) ' if args.dry_run else ''}complete:")
    print(f"  Migrated: {len(results['migrated'])}")
    print(f"  Skipped:  {len(results['skipped'])}")
    print(f"  Errors:   {len(results['errors'])}")

    if results["errors"]:
        print("\nErrors:")
        for name, err in results["errors"].items():
            print(f"  {name}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()

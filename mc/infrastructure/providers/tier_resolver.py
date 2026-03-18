"""Model tier resolver — maps tier references to concrete model strings.

Tier references use the format ``tier:<tier-name>`` (e.g. ``tier:standard-high``).
The resolver fetches the ``model_tiers`` setting from Convex, caches it for 60s,
and returns the mapped model string.

Story 11.1 — AC #3.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

from mc.types import extract_tier_name, is_tier_reference

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)


class TierResolver:
    """Resolves ``tier:`` prefixed model strings to concrete model identifiers.

    Uses the ``model_tiers`` key in the Convex settings table. Results are
    cached for ``CACHE_TTL`` seconds to avoid repeated queries.
    """

    CACHE_TTL = 60.0

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge
        self._cache: dict[str, str | None] = {}
        self._reasoning_cache: dict[str, str] = {}
        self._cache_time: float = 0.0

    def _refresh_cache(self) -> None:
        """Fetch model_tiers and tier_reasoning_levels from Convex."""
        raw_tiers = self._bridge.query("settings:get", {"key": "model_tiers"})
        if raw_tiers is None:
            self._cache = {}
        else:
            try:
                parsed = json.loads(raw_tiers)
                if isinstance(parsed, dict):
                    self._cache = parsed
                else:
                    logger.warning("[tier_resolver] model_tiers is not a dict: %s", type(parsed))
                    self._cache = {}
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("[tier_resolver] Failed to parse model_tiers: %s", exc)
                self._cache = {}

        raw_reasoning = self._bridge.query("settings:get", {"key": "tier_reasoning_levels"})
        if raw_reasoning is None:
            self._reasoning_cache = {}
        else:
            try:
                parsed_r = json.loads(raw_reasoning)
                if isinstance(parsed_r, dict):
                    self._reasoning_cache = parsed_r
                else:
                    logger.warning(
                        "[tier_resolver] tier_reasoning_levels is not a dict: %s", type(parsed_r)
                    )
                    self._reasoning_cache = {}
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("[tier_resolver] Failed to parse tier_reasoning_levels: %s", exc)
                self._reasoning_cache = {}

        self._cache_time = time.monotonic()

    def resolve_model(self, model: str | None) -> str | None:
        """Resolve a model string, handling tier references transparently.

        - If model is None or empty, returns None.
        - If model is NOT a tier reference, returns it unchanged (pass-through).
        - If model IS a tier reference, resolves via cached settings lookup.

        Raises:
            ValueError: If the tier is null, unknown, or settings are missing.
        """
        if not model:
            return None

        if not is_tier_reference(model):
            return model

        tier_name = extract_tier_name(model)
        if tier_name is None:
            raise ValueError(f"Unknown tier: '{model[len('tier:') :]}'")

        # Refresh cache if stale
        if time.monotonic() - self._cache_time > self.CACHE_TTL:
            self._refresh_cache()

        if not self._cache:
            raise ValueError(
                f"Tier '{tier_name}' is not configured (model_tiers setting is missing or empty)"
            )

        if tier_name not in self._cache:
            raise ValueError(f"Unknown tier: '{tier_name}'")

        resolved = self._cache[tier_name]
        if resolved is None:
            raise ValueError(f"Tier '{tier_name}' is not configured (set to null)")

        return resolved

    def resolve_reasoning_level(self, model: str | None) -> str | None:
        """Resolve the reasoning level for a tier reference.

        Returns "low", "medium", "max", or None (off / not configured).
        Non-tier model strings and unconfigured tiers both return None.
        Never raises — missing config is treated as reasoning off.
        """
        if not model or not is_tier_reference(model):
            return None

        tier_name = extract_tier_name(model)
        if tier_name is None:
            return None

        if time.monotonic() - self._cache_time > self.CACHE_TTL:
            try:
                self._refresh_cache()
            except Exception:
                logger.warning("[tier_resolver] Cache refresh failed; using stale reasoning cache")

        level = self._reasoning_cache.get(tier_name)
        return level if level else None  # empty string → None (off)

    def invalidate_cache(self) -> None:
        """Force a refresh on the next resolve_model() or resolve_reasoning_level() call."""
        self._cache_time = 0.0

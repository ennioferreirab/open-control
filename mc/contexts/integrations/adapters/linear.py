"""Concrete Linear platform adapter implementing PlatformAdapter."""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from typing import Any

from mc.contexts.integrations.adapters.linear_client import LinearGraphQLClient
from mc.contexts.integrations.capabilities import PlatformCapability
from mc.contexts.integrations.config import IntegrationConfig
from mc.contexts.integrations.errors import IntegrationError, IntegrationErrorKind
from mc.contexts.integrations.events import (
    MC_COMMENT_PREFIX,
    EventDirection,
    IntegrationEvent,
    IntegrationEventType,
)
from mc.contexts.integrations.status_mapping import resolve_status_inbound

logger = logging.getLogger(__name__)


class LinearAdapter:
    """Linear platform adapter implementing PlatformAdapter protocol."""

    platform_name = "linear"

    capabilities = frozenset(
        {
            PlatformCapability.INGEST_ITEM,
            PlatformCapability.PUBLISH_STATUS,
            PlatformCapability.THREAD_MIRRORING,
            PlatformCapability.STATUS_MAPPING,
            PlatformCapability.BIDIRECTIONAL_COMMENTS,
            PlatformCapability.LABELS_SYNC,
            PlatformCapability.ASSIGNMENT_SYNC,
            PlatformCapability.WEBHOOK_INBOUND,
            PlatformCapability.EXECUTION_RESUME_FROM_COMMENT,
        }
    )

    def __init__(self, config: IntegrationConfig, client: LinearGraphQLClient) -> None:
        self._config = config
        self._client = client
        self._workflow_state_cache: dict[str, list[dict[str, Any]]] = {}

    def supports(self, capability: PlatformCapability) -> bool:
        """Return True if this adapter supports the given capability."""
        return capability in self.capabilities

    # --- Inbound ---

    async def fetch_item(self, external_id: str) -> IntegrationEvent:
        """Fetch a Linear issue and return as a canonical ITEM_CREATED event."""
        issue = await self._client.get_issue(external_id)
        if not issue:
            raise IntegrationError(
                kind=IntegrationErrorKind.NOT_FOUND,
                message=f"Linear issue {external_id} not found",
                platform="linear",
                retryable=False,
            )

        state = issue.get("state", {})
        mc_status = resolve_status_inbound(
            state.get("type", ""),
            self._config.status_mapping,
        )

        labels = [n.get("name", "") for n in issue.get("labels", {}).get("nodes", [])]
        assignee = issue.get("assignee", {})

        return IntegrationEvent(
            event_id=f"fetch-{external_id}-{uuid.uuid4().hex[:8]}",
            event_type=IntegrationEventType.ITEM_CREATED,
            direction=EventDirection.INBOUND,
            timestamp=issue.get("createdAt", ""),
            platform="linear",
            integration_id=self._config.id,
            external_id=external_id,
            title=issue.get("title", ""),
            description=issue.get("description", ""),
            status=state.get("type", ""),
            mc_status=mc_status,
            labels=labels,
            assignee=assignee.get("name") if assignee else None,
            raw_payload=issue,
            idempotency_key=f"linear-fetch-{external_id}",
        )

    async def normalize_webhook(
        self, raw_payload: dict[str, Any], headers: dict[str, str]
    ) -> list[IntegrationEvent]:
        """Parse a Linear webhook payload into canonical events."""
        action = raw_payload.get("action", "")
        entity_type = raw_payload.get("type", "")
        data = raw_payload.get("data", {})

        # Skip events from our own app (loop prevention)
        actor = raw_payload.get("actor", {})
        if actor and actor.get("type") == "application":
            logger.debug("Skipping webhook from application actor (loop prevention)")
            return []

        webhook_id = raw_payload.get("webhookId", "")
        created_at = raw_payload.get("createdAt", data.get("createdAt", ""))

        events: list[IntegrationEvent] = []

        if entity_type == "Issue":
            events = self._normalize_issue_webhook(
                action, data, webhook_id, created_at, raw_payload
            )
        elif entity_type == "Comment":
            events = self._normalize_comment_webhook(
                action, data, webhook_id, created_at, raw_payload
            )
        else:
            logger.debug("Ignoring webhook type=%s action=%s", entity_type, action)

        return events

    def _normalize_issue_webhook(
        self,
        action: str,
        data: dict[str, Any],
        webhook_id: str,
        created_at: str,
        raw_payload: dict[str, Any],
    ) -> list[IntegrationEvent]:
        """Normalize Issue webhooks into canonical events."""
        issue_id = data.get("id", "")
        events: list[IntegrationEvent] = []

        if action == "create":
            state = data.get("state", {})
            state_type = state.get("type", "") if isinstance(state, dict) else ""
            mc_status = resolve_status_inbound(state_type, self._config.status_mapping)
            labels = [lbl.get("name", "") for lbl in data.get("labels", [])]
            assignee = data.get("assignee", {})

            events.append(
                IntegrationEvent(
                    event_id=f"linear-webhook-{webhook_id}-{issue_id}-create",
                    event_type=IntegrationEventType.ITEM_CREATED,
                    direction=EventDirection.INBOUND,
                    timestamp=created_at,
                    platform="linear",
                    integration_id=self._config.id,
                    external_id=issue_id,
                    title=data.get("title", ""),
                    description=data.get("description", ""),
                    status=state_type,
                    mc_status=mc_status,
                    labels=labels,
                    assignee=assignee.get("name")
                    if isinstance(assignee, dict) and assignee
                    else None,
                    raw_payload=raw_payload,
                    idempotency_key=f"linear-issue-create-{issue_id}",
                )
            )

        elif action == "update":
            updated_from = raw_payload.get("updatedFrom", {})

            # Status change
            if "state" in updated_from:
                new_state = data.get("state", {})
                new_state_type = new_state.get("type", "") if isinstance(new_state, dict) else ""
                mc_status = resolve_status_inbound(new_state_type, self._config.status_mapping)

                events.append(
                    IntegrationEvent(
                        event_id=f"linear-webhook-{webhook_id}-{issue_id}-status",
                        event_type=IntegrationEventType.STATUS_CHANGED,
                        direction=EventDirection.INBOUND,
                        timestamp=created_at,
                        platform="linear",
                        integration_id=self._config.id,
                        external_id=issue_id,
                        status=new_state_type,
                        mc_status=mc_status,
                        raw_payload=raw_payload,
                        idempotency_key=f"linear-issue-status-{issue_id}-{created_at}",
                    )
                )

            # Title change
            if "title" in updated_from:
                events.append(
                    IntegrationEvent(
                        event_id=f"linear-webhook-{webhook_id}-{issue_id}-title",
                        event_type=IntegrationEventType.ITEM_UPDATED,
                        direction=EventDirection.INBOUND,
                        timestamp=created_at,
                        platform="linear",
                        integration_id=self._config.id,
                        external_id=issue_id,
                        title=data.get("title", ""),
                        raw_payload=raw_payload,
                        idempotency_key=f"linear-issue-title-{issue_id}-{created_at}",
                    )
                )

            # Description change
            if "description" in updated_from:
                events.append(
                    IntegrationEvent(
                        event_id=f"linear-webhook-{webhook_id}-{issue_id}-desc",
                        event_type=IntegrationEventType.ITEM_UPDATED,
                        direction=EventDirection.INBOUND,
                        timestamp=created_at,
                        platform="linear",
                        integration_id=self._config.id,
                        external_id=issue_id,
                        description=data.get("description", ""),
                        raw_payload=raw_payload,
                        idempotency_key=f"linear-issue-desc-{issue_id}-{created_at}",
                    )
                )

            # Label change
            if "labels" in updated_from or "labelIds" in updated_from:
                labels = [lbl.get("name", "") for lbl in data.get("labels", [])]
                events.append(
                    IntegrationEvent(
                        event_id=f"linear-webhook-{webhook_id}-{issue_id}-labels",
                        event_type=IntegrationEventType.LABEL_CHANGED,
                        direction=EventDirection.INBOUND,
                        timestamp=created_at,
                        platform="linear",
                        integration_id=self._config.id,
                        external_id=issue_id,
                        labels=labels,
                        raw_payload=raw_payload,
                        idempotency_key=f"linear-issue-labels-{issue_id}-{created_at}",
                    )
                )

        elif action == "remove":
            events.append(
                IntegrationEvent(
                    event_id=f"linear-webhook-{webhook_id}-{issue_id}-remove",
                    event_type=IntegrationEventType.ITEM_DELETED,
                    direction=EventDirection.INBOUND,
                    timestamp=created_at,
                    platform="linear",
                    integration_id=self._config.id,
                    external_id=issue_id,
                    raw_payload=raw_payload,
                    idempotency_key=f"linear-issue-remove-{issue_id}",
                )
            )

        return events

    def _normalize_comment_webhook(
        self,
        action: str,
        data: dict[str, Any],
        webhook_id: str,
        created_at: str,
        raw_payload: dict[str, Any],
    ) -> list[IntegrationEvent]:
        """Normalize Comment webhooks into canonical events."""
        comment_id = data.get("id", "")
        issue_id = data.get("issueId", "") or data.get("issue", {}).get("id", "")
        body = data.get("body", "")

        # Skip comments with MC prefix (loop prevention)
        if body.strip().startswith(MC_COMMENT_PREFIX):
            logger.debug("Skipping MC-originated comment %s", comment_id)
            return []

        if action != "create":
            logger.debug("Ignoring comment action=%s", action)
            return []

        user = data.get("user", {})

        return [
            IntegrationEvent(
                event_id=f"linear-webhook-{webhook_id}-comment-{comment_id}",
                event_type=IntegrationEventType.COMMENT_ADDED,
                direction=EventDirection.INBOUND,
                timestamp=created_at,
                platform="linear",
                integration_id=self._config.id,
                external_id=issue_id,
                comment_body=body,
                author=user.get("name", "linear-user") if user else "linear-user",
                raw_payload=raw_payload,
                idempotency_key=f"linear-comment-{comment_id}",
            )
        ]

    async def verify_webhook_signature(
        self, raw_body: bytes, headers: dict[str, str], signing_secret: str
    ) -> bool:
        """Verify Linear webhook HMAC-SHA256 signature."""
        signature = headers.get("linear-signature", headers.get("Linear-Signature", ""))
        if not signature or not signing_secret:
            return False

        expected = hmac.new(
            signing_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    # --- Outbound ---

    async def publish_status_change(
        self, external_id: str, mc_status: str, mapped_status: str
    ) -> None:
        """Update issue status on Linear by resolving workflow state ID."""
        state_id = await self._resolve_workflow_state_id(external_id, mapped_status)
        if not state_id:
            raise IntegrationError(
                kind=IntegrationErrorKind.MAPPING_NOT_FOUND,
                message=f"No Linear workflow state found for type '{mapped_status}'",
                platform="linear",
                retryable=False,
            )
        await self._client.update_issue(external_id, stateId=state_id)
        logger.info("Published status %s→%s for issue %s", mc_status, mapped_status, external_id)

    async def publish_comment(
        self, external_id: str, body: str, author: str | None = None
    ) -> str | None:
        """Post a comment on a Linear issue with MC prefix."""
        prefix = f"**{author}** " if author else ""
        formatted_body = f"{MC_COMMENT_PREFIX} {prefix}{body}"

        result = await self._client.create_comment(external_id, formatted_body)
        comment = result.get("comment", {})
        comment_id = comment.get("id") if comment else None
        logger.info("Published comment to issue %s (id=%s)", external_id, comment_id)
        return comment_id

    async def close_item(
        self, external_id: str, final_status: str, summary: str | None = None
    ) -> None:
        """Transition issue to completion and optionally post summary."""
        if summary:
            await self.publish_comment(external_id, summary, author="MC Summary")

        await self.publish_status_change(external_id, "done", final_status)

    async def publish_labels(self, external_id: str, labels: list[str]) -> None:
        """Sync labels to Linear issue (not implemented in V1)."""
        raise IntegrationError(
            kind=IntegrationErrorKind.CAPABILITY_UNSUPPORTED,
            message="Label sync not yet implemented for outbound",
            platform="linear",
            retryable=False,
        )

    # --- Lifecycle ---

    async def validate_credentials(self) -> bool:
        """Test API key by fetching viewer info."""
        try:
            result = await self._client.execute("query { viewer { id name } }")
            return bool(result.get("viewer", {}).get("id"))
        except Exception:
            logger.exception("Linear credential validation failed")
            return False

    # --- Internal helpers ---

    async def _resolve_workflow_state_id(self, issue_id: str, state_type: str) -> str | None:
        """Resolve concrete workflow state ID from cached team states."""
        # Get the issue to find its team
        issue = await self._client.get_issue(issue_id)
        if not issue:
            logger.warning("[linear] Cannot resolve workflow state: issue %s not found", issue_id)
            return None

        team = issue.get("team") or {}
        team_id = team.get("id", "")

        if not team_id:
            logger.warning("[linear] Issue %s has no team, cannot resolve workflow state", issue_id)
            return None

        # Cache team workflow states
        if team_id not in self._workflow_state_cache:
            states = await self._client.get_team_workflow_states(team_id)
            self._workflow_state_cache[team_id] = states

        # Find the first state matching the target type
        for state in self._workflow_state_cache[team_id]:
            if state.get("type") == state_type:
                return state.get("id")

        return None


def create_linear_adapter(config: IntegrationConfig) -> LinearAdapter:
    """Factory function to create a LinearAdapter from config."""
    if not config.api_key:
        raise IntegrationError(
            kind=IntegrationErrorKind.AUTH_EXPIRED,
            message="Linear API key is required",
            platform="linear",
            retryable=False,
        )
    client = LinearGraphQLClient(config.api_key)
    return LinearAdapter(config, client)

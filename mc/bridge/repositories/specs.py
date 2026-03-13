"""Specs repository — Agent Spec V2 creation, publish, and board bindings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClient


class SpecsRepository:
    """Data access methods for Agent Spec V2 entities in Convex."""

    def __init__(self, client: "BridgeClient") -> None:
        self._client = client

    def create_agent_spec(
        self,
        name: str,
        role: str,
        prompt: str,
        display_name: str | None = None,
        model: str | None = None,
        skills: list[str] | None = None,
        soul: str | None = None,
    ) -> str | None:
        """Create a new Agent Spec V2 record in Convex.

        Args:
            name: Agent name (slug).
            role: Agent role description.
            prompt: Agent system prompt text.
            display_name: Optional human-readable name.
            model: Optional model identifier.
            skills: Optional list of skill names.
            soul: Optional SOUL.md content.

        Returns:
            The new spec document ID, or None if the mutation returned nothing.
        """
        args: dict[str, Any] = {
            "name": name,
            "role": role,
            "prompt": prompt,
        }
        if display_name is not None:
            args["display_name"] = display_name
        if model is not None:
            args["model"] = model
        if skills is not None:
            args["skills"] = skills
        if soul is not None:
            args["soul"] = soul
        return self._client.mutation("agentSpecs:create", args)

    def get_agent_spec_by_name(self, name: str) -> dict[str, Any] | None:
        """Fetch the latest Agent Spec V2 record for an agent by name.

        Returns:
            Spec document dict with snake_case keys, or None if not found.
        """
        return self._client.query("agentSpecs:getByName", {"name": name})

    def publish_agent_spec(self, spec_id: str) -> Any:
        """Publish an Agent Spec V2 record, compiling it into a runtime projection.

        Args:
            spec_id: The Convex document ID of the spec to publish.

        Returns:
            Mutation result (if any).
        """
        return self._client.mutation("agentSpecs:publish", {"spec_id": spec_id})

    def create_board_agent_binding(
        self,
        board_id: str,
        agent_name: str,
    ) -> Any:
        """Create a binding between an agent spec and a board.

        Args:
            board_id: The Convex board document ID.
            agent_name: The agent name to bind.

        Returns:
            Mutation result (if any).
        """
        return self._client.mutation(
            "agentSpecs:bindToBoard",
            {"board_id": board_id, "agent_name": agent_name},
        )

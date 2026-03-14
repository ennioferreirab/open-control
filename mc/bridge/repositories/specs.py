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
        display_name: str | None = None,
        # V1 legacy fields (kept for backward compat)
        prompt: str | None = None,
        model: str | None = None,
        skills: list[str] | None = None,
        soul: str | None = None,
        # V2 fields
        responsibilities: list[str] | None = None,
        non_goals: list[str] | None = None,
        principles: list[str] | None = None,
        working_style: str | None = None,
        quality_rules: list[str] | None = None,
        anti_patterns: list[str] | None = None,
        output_contract: str | None = None,
        tool_policy: str | None = None,
        memory_policy: str | None = None,
        execution_policy: str | None = None,
        review_policy_ref: str | None = None,
    ) -> str | None:
        """Create a new Agent Spec V2 draft record in Convex.

        Args:
            name: Agent name (slug).
            role: Agent role description.
            display_name: Human-readable name (required by createDraft).
            prompt: Optional legacy system prompt text.
            model: Optional model identifier.
            skills: Optional list of skill names.
            soul: Optional SOUL.md content.
            responsibilities: What this agent is responsible for.
            non_goals: What this agent explicitly does NOT do.
            principles: Core principles guiding the agent.
            working_style: Description of how the agent works.
            quality_rules: Rules for quality output.
            anti_patterns: Patterns this agent avoids.
            output_contract: Description of outputs this agent produces.
            tool_policy: Policy for tool usage.
            memory_policy: Policy for memory / context persistence.
            execution_policy: Policy for task execution.
            review_policy_ref: Reference to a review policy.

        Returns:
            The new spec document ID, or None if the mutation returned nothing.
        """
        args: dict[str, Any] = {
            "name": name,
            "role": role,
        }
        if display_name is not None:
            args["display_name"] = display_name
        if prompt is not None:
            args["prompt"] = prompt
        if model is not None:
            args["model"] = model
        if skills is not None:
            args["skills"] = skills
        if soul is not None:
            args["soul"] = soul
        # V2 optional fields
        if responsibilities is not None:
            args["responsibilities"] = responsibilities
        if non_goals is not None:
            args["non_goals"] = non_goals
        if principles is not None:
            args["principles"] = principles
        if working_style is not None:
            args["working_style"] = working_style
        if quality_rules is not None:
            args["quality_rules"] = quality_rules
        if anti_patterns is not None:
            args["anti_patterns"] = anti_patterns
        if output_contract is not None:
            args["output_contract"] = output_contract
        if tool_policy is not None:
            args["tool_policy"] = tool_policy
        if memory_policy is not None:
            args["memory_policy"] = memory_policy
        if execution_policy is not None:
            args["execution_policy"] = execution_policy
        if review_policy_ref is not None:
            args["review_policy_ref"] = review_policy_ref
        return self._client.mutation("agentSpecs:createDraft", args)

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

    def publish_squad_graph(self, graph: dict[str, Any]) -> Any:
        """Publish a complete squad blueprint graph to Convex.

        Args:
            graph: The squad graph structure with squad, agents, workflows,
                   and optional reviewPolicy keys.

        Returns:
            The new squad document ID, or None if the mutation returned nothing.
        """
        return self._client.mutation("squadSpecs:publishGraph", {"graph": graph})

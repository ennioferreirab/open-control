"""Specs repository — Agent Spec V2 creation, publish, and board bindings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.client import BridgeClientProtocol


class SpecsRepository:
    """Data access methods for Agent Spec V2 entities in Convex."""

    def __init__(self, client: BridgeClientProtocol) -> None:
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
        """Publish an Agent Spec V2 and project it into the agents table.

        1. Sets the spec status to "published".
        2. Reads the spec back.
        3. Calls ``agents:publishProjection`` to create/update the runtime agent.

        The agent then appears in ``activeAgents`` immediately.
        """
        self._client.mutation("agentSpecs:publish", {"spec_id": spec_id})

        # Read the published spec to get all fields for projection
        spec = self._client.query("agentSpecs:getDraft", {"spec_id": spec_id})
        if not spec:
            return spec_id

        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        self._client.mutation(
            "agents:publishProjection",
            {
                "name": spec.get("name", ""),
                "display_name": spec.get("display_name", ""),
                "role": spec.get("role", ""),
                "prompt": spec.get("prompt")
                or f"You are {spec.get('display_name', spec.get('name', 'an agent'))}.",
                "soul": spec.get("soul")
                or f"# Soul\n\nI am {spec.get('display_name', spec.get('name', 'an agent'))}.",
                "skills": spec.get("skills") or [],
                "model": spec.get("model"),
                "compiled_from_spec_id": spec_id,
                "compiled_from_version": spec.get("version", 1),
                "compiled_at": now,
            },
        )
        return spec_id

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

    def publish_workflow(
        self,
        squad_spec_id: str,
        workflow: dict[str, Any],
    ) -> Any:
        """Publish a standalone workflow to an existing squad.

        Args:
            squad_spec_id: The Convex document ID of the published squad.
            workflow: Workflow definition with name, steps, and optional exitCriteria.

        Returns:
            The new workflow spec document ID, or None if the mutation returned nothing.
        """
        return self._client.mutation(
            "workflowSpecs:publishStandalone",
            {"squad_spec_id": squad_spec_id, "workflow": workflow},
        )

    def create_review_spec(
        self,
        name: str,
        scope: str,
        criteria: list[dict[str, Any]],
        approval_threshold: float,
        veto_conditions: list[str] | None = None,
        feedback_contract: str | None = None,
        reviewer_policy: str | None = None,
        rejection_routing_policy: str | None = None,
    ) -> str | None:
        """Create and publish a review specification.

        Args:
            name: Slug-safe review spec name.
            scope: One of 'agent', 'workflow', 'execution'.
            criteria: Scoring criteria list.
            approval_threshold: Score threshold (0-1) required to pass.
            veto_conditions: Conditions that auto-reject.
            feedback_contract: Expected feedback format.
            reviewer_policy: Who performs the review.
            rejection_routing_policy: What happens on rejection.

        Returns:
            The new review spec document ID, or None.
        """
        args: dict[str, Any] = {
            "name": name,
            "scope": scope,
            "criteria": criteria,
            "approval_threshold": approval_threshold,
        }
        if veto_conditions is not None:
            args["veto_conditions"] = veto_conditions
        if feedback_contract is not None:
            args["feedback_contract"] = feedback_contract
        if reviewer_policy is not None:
            args["reviewer_policy"] = reviewer_policy
        if rejection_routing_policy is not None:
            args["rejection_routing_policy"] = rejection_routing_policy

        spec_id = self._client.mutation("reviewSpecs:createDraft", args)
        if spec_id:
            self._client.mutation("reviewSpecs:publish", {"spec_id": str(spec_id)})
        return spec_id

    def list_skills(self, available_only: bool = False) -> list[dict[str, Any]]:
        """List all registered skills.

        Args:
            available_only: If True, only return available skills.

        Returns:
            List of skill records.
        """
        skills = self._client.query("skills:list", {}) or []
        if available_only:
            return [s for s in skills if s.get("available")]
        return skills

    def register_skill(
        self,
        name: str,
        description: str,
        content: str,
        source: str = "workspace",
        supported_providers: list[str] | None = None,
        available: bool = True,
        always: bool = False,
        requires: str | None = None,
        metadata: str | None = None,
    ) -> None:
        """Register or update a skill in the database.

        Args:
            name: Skill name slug.
            description: What the skill does and when to use it.
            content: Full skill content (SKILL.md body).
            source: 'builtin' or 'workspace'.
            supported_providers: List of provider names.
            available: Whether the skill is available for use.
            always: Whether the skill is always loaded.
            requires: Optional requirement description.
            metadata: Optional JSON metadata string.
        """
        args: dict[str, Any] = {
            "name": name,
            "description": description,
            "content": content,
            "source": source,
            "supported_providers": supported_providers or ["claude-code"],
            "available": available,
        }
        if always:
            args["always"] = True
        if requires is not None:
            args["requires"] = requires
        if metadata is not None:
            args["metadata"] = metadata
        self._client.mutation("skills:upsertByName", args)

    def update_agent(self, name: str, **updates: Any) -> None:
        """Update an agent's configuration fields.

        Args:
            name: Agent name slug.
            **updates: Fields to update (displayName, role, prompt, soul, skills, model).
        """
        args: dict[str, Any] = {"name": name}
        args.update(updates)
        self._client.mutation("agents:updateConfig", args)

    def delete_skill(self, name: str) -> None:
        """Delete a skill by name from Convex."""
        self._client.mutation("skills:deleteByName", {"name": name})

    def archive_squad(self, squad_spec_id: str) -> None:
        """Archive a squad by setting its status to archived."""
        self._client.mutation("squadSpecs:archiveSquad", {"squad_spec_id": squad_spec_id})

    def archive_workflow(self, workflow_spec_id: str) -> None:
        """Archive a workflow by setting its status to archived."""
        self._client.mutation(
            "workflowSpecs:archiveWorkflow", {"workflow_spec_id": workflow_spec_id}
        )

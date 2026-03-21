"""Async GraphQL client for the Linear API."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LINEAR_API_ENDPOINT = "https://api.linear.app/graphql"
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0


@dataclass(frozen=True)
class LinearAPIError(Exception):
    """Error from the Linear GraphQL API."""

    message: str
    errors: list[dict[str, Any]]


class LinearGraphQLClient:
    """Async GraphQL client for Linear with retry and rate-limit handling."""

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._http = httpx.AsyncClient(
            base_url=LINEAR_API_ENDPOINT,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query/mutation with retry on 429/5xx."""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._http.post("", json=payload)

                if response.status_code == 429:
                    retry_after = float(
                        response.headers.get(
                            "Retry-After", BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                        )
                    )
                    logger.warning(
                        "Linear API rate limited, retrying in %.1fs (attempt %d/%d)",
                        retry_after,
                        attempt,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code >= 500:
                    delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Linear API %d error, retrying in %.1fs (attempt %d/%d)",
                        response.status_code,
                        delay,
                        attempt,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                data = response.json()

                if "errors" in data:
                    error_messages = [e.get("message", "Unknown error") for e in data["errors"]]
                    raise LinearAPIError(
                        message="; ".join(error_messages),
                        errors=data["errors"],
                    )

                return data.get("data", {})

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    logger.warning("Linear API connection error, retrying in %.1fs: %s", delay, e)
                    await asyncio.sleep(delay)

        raise last_error or RuntimeError("Linear API request failed after retries")

    async def get_issue(self, issue_id: str) -> dict[str, Any]:
        """Fetch full issue details including state, team, labels, comments."""
        query = """
        query GetIssue($id: String!) {
          issue(id: $id) {
            id
            identifier
            title
            description
            url
            state {
              id
              name
              type
            }
            team {
              id
              name
              key
            }
            assignee {
              id
              name
              email
            }
            labels {
              nodes {
                id
                name
                color
              }
            }
            comments {
              nodes {
                id
                body
                user {
                  id
                  name
                }
                createdAt
              }
            }
            createdAt
            updatedAt
          }
        }
        """
        result = await self.execute(query, {"id": issue_id})
        return result.get("issue", {})

    async def create_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        """Create a markdown comment on an issue."""
        query = """
        mutation CreateComment($issueId: String!, $body: String!) {
          commentCreate(input: { issueId: $issueId, body: $body }) {
            success
            comment {
              id
              body
              createdAt
            }
          }
        }
        """
        result = await self.execute(query, {"issueId": issue_id, "body": body})
        return result.get("commentCreate", {})

    async def update_issue(self, issue_id: str, **fields: Any) -> dict[str, Any]:
        """Update issue fields (stateId, title, description, etc.)."""
        query = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue {
              id
              title
              state {
                id
                name
                type
              }
            }
          }
        }
        """
        result = await self.execute(query, {"id": issue_id, "input": fields})
        return result.get("issueUpdate", {})

    async def get_team_workflow_states(self, team_id: str) -> list[dict[str, Any]]:
        """Return all workflow states for a team with id, name, type."""
        query = """
        query GetTeamStates($teamId: String!) {
          team(id: $teamId) {
            states {
              nodes {
                id
                name
                type
                position
              }
            }
          }
        }
        """
        result = await self.execute(query, {"teamId": team_id})
        team = result.get("team", {})
        states = team.get("states", {})
        return states.get("nodes", [])

    async def close(self) -> None:
        """Shut down the HTTP client."""
        await self._http.aclose()

"""Realistic Linear webhook payload fixtures for testing."""

from __future__ import annotations


def issue_created_webhook(
    issue_id: str = "issue-123",
    title: str = "Fix login bug",
    description: str = "Users can't login on mobile",
    state_type: str = "unstarted",
    url: str = "https://linear.app/team/issue-123",
) -> dict:
    """Issue creation webhook payload."""
    return {
        "action": "create",
        "type": "Issue",
        "createdAt": "2026-03-21T12:00:00.000Z",
        "webhookId": "webhook-001",
        "data": {
            "id": issue_id,
            "title": title,
            "description": description,
            "url": url,
            "state": {"id": "state-1", "name": "Todo", "type": state_type},
            "team": {"id": "team-1", "name": "Engineering", "key": "ENG"},
            "labels": [{"id": "label-1", "name": "bug", "color": "#FF0000"}],
            "assignee": {"id": "user-1", "name": "Alice", "email": "alice@co.com"},
            "createdAt": "2026-03-21T12:00:00.000Z",
        },
        "actor": {"id": "user-1", "name": "Alice", "type": "user"},
    }


def issue_status_changed_webhook(
    issue_id: str = "issue-123",
    new_state_type: str = "started",
) -> dict:
    """Issue status change webhook payload."""
    return {
        "action": "update",
        "type": "Issue",
        "createdAt": "2026-03-21T13:00:00.000Z",
        "webhookId": "webhook-002",
        "data": {
            "id": issue_id,
            "title": "Fix login bug",
            "state": {"id": "state-2", "name": "In Progress", "type": new_state_type},
            "team": {"id": "team-1", "name": "Engineering", "key": "ENG"},
        },
        "updatedFrom": {"state": {"id": "state-1", "name": "Todo", "type": "unstarted"}},
        "actor": {"id": "user-1", "name": "Alice", "type": "user"},
    }


def issue_title_changed_webhook(
    issue_id: str = "issue-123",
    new_title: str = "Fix login bug on mobile and desktop",
) -> dict:
    """Issue title change webhook payload."""
    return {
        "action": "update",
        "type": "Issue",
        "createdAt": "2026-03-21T13:30:00.000Z",
        "webhookId": "webhook-003",
        "data": {
            "id": issue_id,
            "title": new_title,
        },
        "updatedFrom": {"title": "Fix login bug"},
        "actor": {"id": "user-1", "name": "Alice", "type": "user"},
    }


def issue_labels_changed_webhook(
    issue_id: str = "issue-123",
    labels: list[dict] | None = None,
) -> dict:
    """Issue labels change webhook payload."""
    return {
        "action": "update",
        "type": "Issue",
        "createdAt": "2026-03-21T14:00:00.000Z",
        "webhookId": "webhook-004",
        "data": {
            "id": issue_id,
            "labels": labels
            or [
                {"id": "label-1", "name": "bug"},
                {"id": "label-2", "name": "critical"},
            ],
        },
        "updatedFrom": {"labelIds": ["label-1"]},
        "actor": {"id": "user-1", "name": "Alice", "type": "user"},
    }


def comment_created_webhook(
    issue_id: str = "issue-123",
    comment_id: str = "comment-456",
    body: str = "I'll look into this today",
    user_name: str = "Bob",
) -> dict:
    """Comment creation webhook payload."""
    return {
        "action": "create",
        "type": "Comment",
        "createdAt": "2026-03-21T14:30:00.000Z",
        "webhookId": "webhook-005",
        "data": {
            "id": comment_id,
            "body": body,
            "issueId": issue_id,
            "user": {"id": "user-2", "name": user_name},
            "createdAt": "2026-03-21T14:30:00.000Z",
        },
        "actor": {"id": "user-2", "name": user_name, "type": "user"},
    }


def mc_comment_webhook(issue_id: str = "issue-123") -> dict:
    """Comment from MC (should be skipped by loop prevention)."""
    return comment_created_webhook(
        issue_id=issue_id,
        comment_id="comment-mc-1",
        body="[MC] **agent** Step completed: Fixed the login bug",
        user_name="MC Bot",
    )


def application_actor_webhook() -> dict:
    """Webhook from application actor (should be skipped)."""
    payload = issue_created_webhook()
    payload["actor"] = {"id": "app-1", "name": "MC Integration", "type": "application"}
    return payload


def issue_removed_webhook(issue_id: str = "issue-123") -> dict:
    """Issue removal webhook payload."""
    return {
        "action": "remove",
        "type": "Issue",
        "createdAt": "2026-03-21T15:00:00.000Z",
        "webhookId": "webhook-006",
        "data": {"id": issue_id},
        "actor": {"id": "user-1", "name": "Alice", "type": "user"},
    }

"""Structured workflow review-result parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ReviewResult:
    """Normalized reviewer verdict returned by workflow review steps."""

    verdict: Literal["approved", "rejected"]
    issues: list[str]
    strengths: list[str]
    scores: dict[str, Any]
    vetoes_triggered: list[str]
    recommended_return_step: str | None


def _strip_code_fences(payload: str) -> str:
    text = payload.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def parse_review_result(payload: str | dict[str, Any]) -> ReviewResult:
    """Parse the structured result emitted by a workflow reviewer step."""
    if isinstance(payload, str):
        raw_payload = _strip_code_fences(payload)
        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Review result must be a valid JSON object") from exc
    else:
        data = payload

    if not isinstance(data, dict):
        raise ValueError("Review result must be a valid JSON object")

    verdict = data.get("verdict")
    if verdict not in ("approved", "rejected"):
        raise ValueError("Review result requires 'verdict' of 'approved' or 'rejected'")

    issues = data.get("issues") or []
    strengths = data.get("strengths") or []
    scores = data.get("scores") or {}
    vetoes = data.get("vetoesTriggered") or []
    recommended_return_step = data.get("recommendedReturnStep")

    if not isinstance(issues, list):
        raise ValueError("Review result 'issues' must be a list")
    if not isinstance(strengths, list):
        raise ValueError("Review result 'strengths' must be a list")
    if not isinstance(scores, dict):
        raise ValueError("Review result 'scores' must be an object")
    if not isinstance(vetoes, list):
        raise ValueError("Review result 'vetoesTriggered' must be a list")
    if recommended_return_step is not None and not isinstance(recommended_return_step, str):
        raise ValueError("Review result 'recommendedReturnStep' must be a string or null")

    return ReviewResult(
        verdict=verdict,
        issues=[str(issue) for issue in issues],
        strengths=[str(strength) for strength in strengths],
        scores=scores,
        vetoes_triggered=[str(veto) for veto in vetoes],
        recommended_return_step=recommended_return_step,
    )

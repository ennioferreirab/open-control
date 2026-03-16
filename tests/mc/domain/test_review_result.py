"""Tests for structured workflow review-result parsing."""

from __future__ import annotations

import pytest

from mc.domain.workflow.review_result import ReviewResult, parse_review_result


def test_parse_review_result_accepts_approved_payload() -> None:
    result = parse_review_result(
        """
        {
          "verdict": "approved",
          "issues": [],
          "strengths": ["Clear CTA"],
          "scores": {"overall": 0.97},
          "vetoesTriggered": [],
          "recommendedReturnStep": null
        }
        """
    )

    assert result == ReviewResult(
        verdict="approved",
        issues=[],
        strengths=["Clear CTA"],
        scores={"overall": 0.97},
        vetoes_triggered=[],
        recommended_return_step=None,
    )


def test_parse_review_result_accepts_rejected_payload() -> None:
    result = parse_review_result(
        """
        {
          "verdict": "rejected",
          "issues": ["Fix alignment"],
          "strengths": [],
          "scores": {"overall": 0.41},
          "vetoesTriggered": ["alignment"],
          "recommendedReturnStep": "step-write-1"
        }
        """
    )

    assert result.verdict == "rejected"
    assert result.issues == ["Fix alignment"]
    assert result.vetoes_triggered == ["alignment"]
    assert result.recommended_return_step == "step-write-1"


def test_parse_review_result_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="valid JSON object"):
        parse_review_result("not-json")


def test_parse_review_result_requires_verdict() -> None:
    with pytest.raises(ValueError, match="requires 'verdict'"):
        parse_review_result(
            """
            {
              "issues": [],
              "strengths": [],
              "scores": {},
              "vetoesTriggered": [],
              "recommendedReturnStep": null
            }
            """
        )

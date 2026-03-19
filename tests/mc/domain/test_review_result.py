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


def test_parse_review_result_extracts_json_from_prose() -> None:
    """Parser should extract JSON when agent wraps it in commentary."""
    result = parse_review_result(
        "Here is my review:\n\n"
        '{"verdict": "rejected", "issues": ["Missing data"], '
        '"strengths": ["Good structure"], "scores": {"accuracy": 0.3}, '
        '"vetoesTriggered": [], "recommendedReturnStep": "write"}'
        "\n\nHope this helps!"
    )
    assert result.verdict == "rejected"
    assert result.issues == ["Missing data"]
    assert result.recommended_return_step == "write"


def test_parse_review_result_handles_braces_in_strings() -> None:
    """JSON with braces inside string values must parse correctly."""
    result = parse_review_result(
        "Review:\n"
        '{"verdict": "rejected", "issues": ["Fix {alignment} issue"], '
        '"strengths": [], "scores": {}, '
        '"vetoesTriggered": [], "recommendedReturnStep": null}'
    )
    assert result.verdict == "rejected"
    assert result.issues == ["Fix {alignment} issue"]


def test_parse_review_result_strips_markdown_fences_with_prose() -> None:
    """Markdown fences around JSON with trailing prose."""
    result = parse_review_result(
        "```json\n"
        '{"verdict": "approved", "issues": [], "strengths": ["Clean"], '
        '"scores": {"overall": 0.9}, "vetoesTriggered": [], '
        '"recommendedReturnStep": null}\n'
        "```"
    )
    assert result.verdict == "approved"


def test_parse_review_result_rejects_no_json_at_all() -> None:
    with pytest.raises(ValueError, match="valid JSON object"):
        parse_review_result("This is just text with no JSON at all.")


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

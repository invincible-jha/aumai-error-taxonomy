"""Tests for aumai_error_taxonomy.suggestions — RecoverySuggester and RecoverySuggestion."""

from __future__ import annotations

import json

import pytest

from aumai_llm_core import LLMClient, ModelConfig, MockProvider

from aumai_error_taxonomy.models import AgentError, ErrorCategory
from aumai_error_taxonomy.suggestions import (
    RecoverySuggester,
    RecoverySuggestion,
    _CATEGORY_STATIC_SUGGESTIONS,
    _STATIC_SUGGESTIONS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_suggester(responses: list[str] | None = None) -> RecoverySuggester:
    """Return a RecoverySuggester backed by MockProvider with *responses*."""
    mock_response = json.dumps(
        {
            "suggestion": "Test suggestion from mock.",
            "confidence": "high",
            "steps": ["Step one.", "Step two."],
            "references": ["https://docs.example.com/error"],
        }
    )
    effective_responses = responses if responses is not None else [mock_response]
    mock_provider = MockProvider(responses=effective_responses)
    config = ModelConfig(provider="mock", model_id="mock-model")
    client = LLMClient(config)
    client._provider = mock_provider  # type: ignore[attr-defined]
    return RecoverySuggester(client=client)


def _make_agent_error(code: int = 103) -> AgentError:
    return AgentError(
        code=code,
        category=ErrorCategory.model,
        name="model_timeout",
        description="Model timed out.",
        retryable=True,
        severity="high",
    )


# ---------------------------------------------------------------------------
# RecoverySuggestion model tests
# ---------------------------------------------------------------------------


class TestRecoverySuggestionModel:
    def test_create_with_all_fields(self) -> None:
        suggestion = RecoverySuggestion(
            suggestion="Retry after back-off.",
            confidence="high",
            steps=["Wait 2 seconds.", "Retry the request."],
            references=["https://docs.example.com"],
        )
        assert suggestion.suggestion == "Retry after back-off."
        assert suggestion.confidence == "high"
        assert len(suggestion.steps) == 2
        assert len(suggestion.references) == 1

    def test_default_steps_and_references_are_empty(self) -> None:
        suggestion = RecoverySuggestion(
            suggestion="Do something.",
            confidence="low",
        )
        assert suggestion.steps == []
        assert suggestion.references == []

    def test_confidence_values(self) -> None:
        for level in ["high", "medium", "low"]:
            s = RecoverySuggestion(suggestion="x", confidence=level)
            assert s.confidence == level

    def test_is_pydantic_model(self) -> None:
        from pydantic import BaseModel

        assert issubclass(RecoverySuggestion, BaseModel)

    def test_model_dump_is_serialisable(self) -> None:
        suggestion = RecoverySuggestion(
            suggestion="Check logs.", confidence="medium", steps=["Look at stdout."]
        )
        data = suggestion.model_dump()
        assert isinstance(data, dict)
        assert "suggestion" in data
        assert "confidence" in data
        assert "steps" in data
        assert "references" in data


# ---------------------------------------------------------------------------
# RecoverySuggester initialisation tests
# ---------------------------------------------------------------------------


class TestRecoverySuggesterInit:
    def test_default_init_uses_mock_provider(self) -> None:
        suggester = RecoverySuggester()
        assert suggester.client is not None

    def test_custom_client_stored(self) -> None:
        mock_provider = MockProvider()
        config = ModelConfig(provider="mock", model_id="mock-model")
        client = LLMClient(config)
        client._provider = mock_provider  # type: ignore[attr-defined]
        suggester = RecoverySuggester(client=client)
        assert suggester.client is client


# ---------------------------------------------------------------------------
# suggest() via MockProvider (LLM path)
# ---------------------------------------------------------------------------


class TestSuggestViaMock:
    async def test_suggest_returns_recovery_suggestion(self) -> None:
        suggester = _make_suggester()
        result = await suggester.suggest(error_code=103)
        assert isinstance(result, RecoverySuggestion)

    async def test_suggest_returns_non_empty_suggestion(self) -> None:
        suggester = _make_suggester()
        result = await suggester.suggest(error_code=103)
        assert len(result.suggestion) > 0

    async def test_suggest_confidence_is_valid(self) -> None:
        suggester = _make_suggester()
        result = await suggester.suggest(error_code=103)
        assert result.confidence in {"high", "medium", "low"}

    async def test_suggest_steps_is_list(self) -> None:
        suggester = _make_suggester()
        result = await suggester.suggest(error_code=103)
        assert isinstance(result.steps, list)

    async def test_suggest_references_is_list(self) -> None:
        suggester = _make_suggester()
        result = await suggester.suggest(error_code=103)
        assert isinstance(result.references, list)

    async def test_suggest_with_context(self) -> None:
        suggester = _make_suggester()
        result = await suggester.suggest(
            error_code=103, context="model took 30s to respond"
        )
        assert isinstance(result, RecoverySuggestion)

    async def test_suggest_with_agent_id(self) -> None:
        suggester = _make_suggester()
        result = await suggester.suggest(error_code=103, agent_id="agent-abc")
        assert isinstance(result, RecoverySuggestion)

    async def test_suggest_for_error_convenience(self) -> None:
        suggester = _make_suggester()
        error = _make_agent_error()
        result = await suggester.suggest_for_error(error=error, context="ctx")
        assert isinstance(result, RecoverySuggestion)

    async def test_suggest_calls_llm_once(self) -> None:
        mock_response = json.dumps(
            {"suggestion": "x", "confidence": "low", "steps": [], "references": []}
        )
        mock_provider = MockProvider(responses=[mock_response])
        config = ModelConfig(provider="mock", model_id="mock-model")
        client = LLMClient(config)
        client._provider = mock_provider  # type: ignore[attr-defined]
        suggester = RecoverySuggester(client=client)
        await suggester.suggest(error_code=101)
        assert mock_provider.call_count == 1


# ---------------------------------------------------------------------------
# Fallback to static suggestions
# ---------------------------------------------------------------------------


class TestSuggestFallback:
    async def test_falls_back_when_llm_response_is_invalid_json(self) -> None:
        # MockProvider will return non-JSON text.
        bad_responses = ["This is not JSON at all."]
        suggester = _make_suggester(responses=bad_responses)
        result = await suggester.suggest(error_code=103)
        # Should fall back to static suggestion without raising.
        assert isinstance(result, RecoverySuggestion)

    async def test_fallback_suggestion_non_empty(self) -> None:
        bad_responses = ["{{invalid"]
        suggester = _make_suggester(responses=bad_responses)
        result = await suggester.suggest(error_code=101)
        assert len(result.suggestion) > 0

    async def test_suggest_static_returns_recovery_suggestion(self) -> None:
        suggester = _make_suggester()
        result = suggester.suggest_static(error_code=103)
        assert isinstance(result, RecoverySuggestion)

    async def test_suggest_static_known_code_returns_specific(self) -> None:
        suggester = _make_suggester()
        result = suggester.suggest_static(error_code=103)
        assert result is _STATIC_SUGGESTIONS[103]

    async def test_suggest_static_unknown_code_returns_generic(self) -> None:
        suggester = _make_suggester()
        result = suggester.suggest_static(error_code=9999)
        assert isinstance(result, RecoverySuggestion)
        assert "taxonomy" in result.suggestion.lower() or len(result.steps) > 0

    async def test_suggest_static_uses_category_fallback(self) -> None:
        # Use a code that is in the registry but not in _STATIC_SUGGESTIONS.
        codes_not_in_static = [
            code
            for code in [102, 104, 105, 106, 204, 205, 303, 304, 305, 402, 403, 405,
                         406, 502, 503, 504, 602, 603, 604, 605, 606]
            if code not in _STATIC_SUGGESTIONS
        ]
        if codes_not_in_static:
            code = codes_not_in_static[0]
            suggester = _make_suggester()
            result = suggester.suggest_static(error_code=code)
            assert isinstance(result, RecoverySuggestion)


# ---------------------------------------------------------------------------
# Static suggestion table completeness tests
# ---------------------------------------------------------------------------


class TestStaticSuggestionTable:
    def test_static_suggestions_is_dict(self) -> None:
        assert isinstance(_STATIC_SUGGESTIONS, dict)

    def test_all_static_suggestions_are_recovery_suggestion(self) -> None:
        for code, suggestion in _STATIC_SUGGESTIONS.items():
            assert isinstance(suggestion, RecoverySuggestion), (
                f"Code {code} static suggestion is not a RecoverySuggestion"
            )

    def test_all_static_confidence_values_are_valid(self) -> None:
        for code, suggestion in _STATIC_SUGGESTIONS.items():
            assert suggestion.confidence in {"high", "medium", "low"}, (
                f"Code {code} has invalid confidence: {suggestion.confidence!r}"
            )

    def test_all_static_suggestions_have_steps(self) -> None:
        for code, suggestion in _STATIC_SUGGESTIONS.items():
            assert len(suggestion.steps) > 0, (
                f"Code {code} static suggestion has no steps"
            )

    def test_category_static_suggestions_cover_all_categories(self) -> None:
        for category in ErrorCategory:
            assert category in _CATEGORY_STATIC_SUGGESTIONS, (
                f"Category {category.value} has no static suggestion"
            )

    def test_all_category_suggestions_have_steps(self) -> None:
        for category, suggestion in _CATEGORY_STATIC_SUGGESTIONS.items():
            assert len(suggestion.steps) > 0, (
                f"Category {category.value} static suggestion has no steps"
            )


# ---------------------------------------------------------------------------
# JSON parsing edge cases
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_parse_valid_json(self) -> None:
        suggester = _make_suggester()
        payload = json.dumps(
            {
                "suggestion": "Do X.",
                "confidence": "high",
                "steps": ["A", "B"],
                "references": [],
            }
        )
        result = suggester._parse_response(payload)
        assert result.suggestion == "Do X."
        assert result.confidence == "high"

    def test_parse_strips_markdown_fences(self) -> None:
        suggester = _make_suggester()
        payload = "```json\n" + json.dumps(
            {"suggestion": "Do Y.", "confidence": "medium", "steps": [], "references": []}
        ) + "\n```"
        result = suggester._parse_response(payload)
        assert result.suggestion == "Do Y."

    def test_parse_normalises_confidence_to_low_for_unknown(self) -> None:
        suggester = _make_suggester()
        payload = json.dumps(
            {"suggestion": "Do Z.", "confidence": "EXTREME", "steps": [], "references": []}
        )
        result = suggester._parse_response(payload)
        assert result.confidence == "low"

    def test_parse_invalid_json_raises_value_error(self) -> None:
        suggester = _make_suggester()
        with pytest.raises((ValueError, Exception)):
            suggester._parse_response("not json at all")

    def test_parse_json_array_raises_value_error(self) -> None:
        suggester = _make_suggester()
        with pytest.raises(ValueError):
            suggester._parse_response("[1, 2, 3]")

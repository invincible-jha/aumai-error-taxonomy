"""Comprehensive CLI tests for aumai-error-taxonomy."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from aumai_error_taxonomy.cli import main, _format_error_row, _resolve_exception
from aumai_error_taxonomy.core import lookup_error
from aumai_error_taxonomy.models import ErrorCategory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# main group tests
# ---------------------------------------------------------------------------


class TestMainGroup:
    def test_version_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "lookup" in result.output
        assert "classify" in result.output


# ---------------------------------------------------------------------------
# list command tests
# ---------------------------------------------------------------------------


class TestListCommand:
    def test_list_exits_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0

    def test_list_contains_error_codes(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list"])
        assert "101" in result.output

    def test_list_contains_categories(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list"])
        assert "model" in result.output

    def test_list_json_output_valid_json(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_list_json_contains_error_entries(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list", "--json"])
        data = json.loads(result.output)
        assert len(data) > 0

    def test_list_json_entry_has_code(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list", "--json"])
        data = json.loads(result.output)
        for entry in data:
            assert "code" in entry

    def test_list_json_entry_has_category(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list", "--json"])
        data = json.loads(result.output)
        for entry in data:
            assert "category" in entry

    def test_list_filter_by_model_category(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list", "--category", "model"])
        assert result.exit_code == 0
        # All rows should be model category
        assert "model" in result.output

    def test_list_filter_by_security_category(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list", "--category", "security"])
        assert result.exit_code == 0
        assert "security" in result.output

    def test_list_filter_json_only_matching(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list", "--category", "model", "--json"])
        data = json.loads(result.output)
        for entry in data:
            assert entry["category"] == "model"

    def test_list_short_category_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list", "-c", "tool"])
        assert result.exit_code == 0

    def test_list_no_results_message(self, runner: CliRunner) -> None:
        """Filter for an invalid category should fail the choice validation."""
        result = runner.invoke(main, ["list", "--category", "unknown_category"])
        assert result.exit_code != 0

    def test_list_output_has_header(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list"])
        assert "CODE" in result.output

    def test_list_all_categories_present(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["list"])
        for cat in ["model", "tool", "security", "resource", "orchestration", "data"]:
            assert cat in result.output

    @pytest.mark.parametrize("category", ["model", "tool", "security", "resource", "orchestration", "data"])
    def test_list_each_category(self, runner: CliRunner, category: str) -> None:
        result = runner.invoke(main, ["list", "--category", category])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# lookup command tests
# ---------------------------------------------------------------------------


class TestLookupCommand:
    def test_lookup_known_code_exit_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "101"])
        assert result.exit_code == 0

    def test_lookup_shows_code_name(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "101"])
        assert "model_not_found" in result.output

    def test_lookup_shows_description(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "101"])
        assert "Description" in result.output

    def test_lookup_shows_retryable(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "101"])
        assert "Retryable" in result.output

    def test_lookup_shows_severity(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "101"])
        assert "Severity" in result.output

    def test_lookup_unknown_code_exit_one(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "9999"])
        assert result.exit_code == 1

    def test_lookup_unknown_code_error_message(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "9999"])
        assert "9999" in result.output or "9999" in (result.stderr or "")

    def test_lookup_json_flag_valid_json(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "101", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_lookup_json_has_error_key(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "101", "--json"])
        data = json.loads(result.output)
        assert "error" in data

    def test_lookup_json_error_code_matches(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "201", "--json"])
        data = json.loads(result.output)
        assert data["error"]["code"] == 201

    def test_lookup_json_has_timestamp(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "101", "--json"])
        data = json.loads(result.output)
        assert "timestamp" in data["error"]

    def test_lookup_security_code_301(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "301"])
        assert result.exit_code == 0
        assert "auth_failed" in result.output

    def test_lookup_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lookup", "--help"])
        assert result.exit_code == 0
        assert "code" in result.output.lower()


# ---------------------------------------------------------------------------
# classify command tests
# ---------------------------------------------------------------------------


class TestClassifyCommand:
    def test_classify_timeout_error(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "TimeoutError"])
        assert result.exit_code == 0

    def test_classify_timeout_maps_to_103(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "TimeoutError"])
        assert "103" in result.output

    def test_classify_permission_error(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "PermissionError"])
        assert result.exit_code == 0
        assert "302" in result.output

    def test_classify_value_error(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "ValueError"])
        assert result.exit_code == 0
        assert "601" in result.output

    def test_classify_unknown_exception_uses_fallback(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "CompletelyUnknownException123"])
        assert result.exit_code == 0
        # Should fallback gracefully

    def test_classify_json_flag_valid_json(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "TimeoutError", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_classify_json_has_error_key(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "TimeoutError", "--json"])
        data = json.loads(result.output)
        assert "error" in data

    def test_classify_shows_mapping_description(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "TimeoutError"])
        assert "TimeoutError" in result.output

    def test_classify_file_not_found_maps_correctly(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "FileNotFoundError"])
        assert result.exit_code == 0
        assert "602" in result.output

    def test_classify_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["classify", "--help"])
        assert result.exit_code == 0

    @pytest.mark.parametrize("exc_name,expected_code", [
        ("TimeoutError", "103"),
        ("PermissionError", "302"),
        ("FileNotFoundError", "602"),
        ("MemoryError", "401"),
        ("RecursionError", "501"),
        ("ValueError", "601"),
        ("TypeError", "203"),
    ])
    def test_classify_parametrized(
        self, runner: CliRunner, exc_name: str, expected_code: str
    ) -> None:
        result = runner.invoke(main, ["classify", exc_name])
        assert result.exit_code == 0
        assert expected_code in result.output


# ---------------------------------------------------------------------------
# _format_error_row helper tests
# ---------------------------------------------------------------------------


class TestFormatErrorRow:
    def test_returns_string(self) -> None:
        error = lookup_error(101)
        result = _format_error_row(error)
        assert isinstance(result, str)

    def test_contains_error_code(self) -> None:
        error = lookup_error(101)
        result = _format_error_row(error)
        assert "101" in result

    def test_contains_error_name(self) -> None:
        error = lookup_error(101)
        result = _format_error_row(error)
        assert "model_not_found" in result

    def test_contains_retry_label_for_retryable(self) -> None:
        error = lookup_error(103)  # retryable
        result = _format_error_row(error)
        assert "retry" in result

    def test_contains_no_retry_label_for_non_retryable(self) -> None:
        error = lookup_error(101)  # not retryable
        result = _format_error_row(error)
        assert "no-retry" in result


# ---------------------------------------------------------------------------
# _resolve_exception helper tests
# ---------------------------------------------------------------------------


class TestResolveException:
    def test_resolve_timeout_error(self) -> None:
        result = _resolve_exception("TimeoutError")
        assert result is TimeoutError

    def test_resolve_value_error(self) -> None:
        result = _resolve_exception("ValueError")
        assert result is ValueError

    def test_resolve_unknown_returns_none(self) -> None:
        result = _resolve_exception("CompletelyUnknown12345")
        assert result is None

    def test_resolve_is_subclass_of_base_exception(self) -> None:
        result = _resolve_exception("Exception")
        assert result is not None
        assert issubclass(result, BaseException)

    def test_resolve_non_exception_type_returns_none(self) -> None:
        result = _resolve_exception("int")  # int is not a BaseException subclass
        assert result is None

    def test_resolve_file_not_found_error(self) -> None:
        result = _resolve_exception("FileNotFoundError")
        assert result is FileNotFoundError

"""Comprehensive tests for aumai_error_taxonomy core module."""

from __future__ import annotations

import socket
import urllib.error

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from aumai_error_taxonomy.core import (
    ERROR_REGISTRY,
    AgentErrorException,
    UnknownErrorCode,
    classify_exception,
    create_error_response,
    errors_by_category,
    lookup_error,
)
from aumai_error_taxonomy.models import AgentError, ErrorCategory, ErrorRegistry


# ---------------------------------------------------------------------------
# ERROR_REGISTRY tests
# ---------------------------------------------------------------------------


class TestErrorRegistry:
    """Tests for the module-level ERROR_REGISTRY dict."""

    def test_registry_is_not_empty(self) -> None:
        assert len(ERROR_REGISTRY) > 0

    def test_registry_has_model_errors(self) -> None:
        model_errors = [e for e in ERROR_REGISTRY.values() if e.category == ErrorCategory.model]
        assert len(model_errors) > 0

    def test_registry_has_tool_errors(self) -> None:
        tool_errors = [e for e in ERROR_REGISTRY.values() if e.category == ErrorCategory.tool]
        assert len(tool_errors) > 0

    def test_registry_has_security_errors(self) -> None:
        security_errors = [e for e in ERROR_REGISTRY.values() if e.category == ErrorCategory.security]
        assert len(security_errors) > 0

    def test_registry_has_resource_errors(self) -> None:
        resource_errors = [e for e in ERROR_REGISTRY.values() if e.category == ErrorCategory.resource]
        assert len(resource_errors) > 0

    def test_registry_has_orchestration_errors(self) -> None:
        orch_errors = [e for e in ERROR_REGISTRY.values() if e.category == ErrorCategory.orchestration]
        assert len(orch_errors) > 0

    def test_registry_has_data_errors(self) -> None:
        data_errors = [e for e in ERROR_REGISTRY.values() if e.category == ErrorCategory.data]
        assert len(data_errors) > 0

    def test_registry_keys_are_integers(self) -> None:
        for key in ERROR_REGISTRY.keys():
            assert isinstance(key, int)

    def test_registry_values_are_agent_errors(self) -> None:
        for value in ERROR_REGISTRY.values():
            assert isinstance(value, AgentError)

    def test_known_code_101_present(self) -> None:
        assert 101 in ERROR_REGISTRY

    def test_known_code_201_present(self) -> None:
        assert 201 in ERROR_REGISTRY

    def test_known_code_301_present(self) -> None:
        assert 301 in ERROR_REGISTRY

    def test_known_code_401_present(self) -> None:
        assert 401 in ERROR_REGISTRY

    def test_known_code_501_present(self) -> None:
        assert 501 in ERROR_REGISTRY

    def test_known_code_601_present(self) -> None:
        assert 601 in ERROR_REGISTRY

    def test_model_not_found_101(self) -> None:
        error = ERROR_REGISTRY[101]
        assert error.name == "model_not_found"
        assert error.category == ErrorCategory.model

    def test_auth_failed_301(self) -> None:
        error = ERROR_REGISTRY[301]
        assert error.name == "auth_failed"
        assert error.severity == "critical"

    def test_security_errors_are_non_retryable(self) -> None:
        security_errors = [e for e in ERROR_REGISTRY.values() if e.category == ErrorCategory.security]
        for error in security_errors:
            assert error.retryable is False, f"{error.name} should not be retryable"

    def test_model_timeout_is_retryable(self) -> None:
        error = ERROR_REGISTRY[103]
        assert error.retryable is True


# ---------------------------------------------------------------------------
# lookup_error tests
# ---------------------------------------------------------------------------


class TestLookupError:
    """Tests for the lookup_error function."""

    def test_lookup_known_code(self) -> None:
        error = lookup_error(101)
        assert isinstance(error, AgentError)

    def test_lookup_returns_correct_name(self) -> None:
        error = lookup_error(101)
        assert error.name == "model_not_found"

    def test_lookup_unknown_code_raises(self) -> None:
        with pytest.raises(UnknownErrorCode):
            lookup_error(9999)

    def test_lookup_zero_raises(self) -> None:
        with pytest.raises(UnknownErrorCode):
            lookup_error(0)

    def test_lookup_negative_raises(self) -> None:
        with pytest.raises(UnknownErrorCode):
            lookup_error(-1)

    def test_lookup_all_known_codes(self) -> None:
        for code in ERROR_REGISTRY.keys():
            error = lookup_error(code)
            assert error.code == code

    def test_unknown_error_code_is_key_error(self) -> None:
        with pytest.raises(KeyError):
            lookup_error(9999)

    def test_lookup_201_tool_not_found(self) -> None:
        error = lookup_error(201)
        assert error.name == "tool_not_found"
        assert error.category == ErrorCategory.tool

    def test_lookup_302_permission_denied(self) -> None:
        error = lookup_error(302)
        assert error.name == "permission_denied"

    def test_lookup_601_data_schema_violation(self) -> None:
        error = lookup_error(601)
        assert error.name == "data_schema_violation"

    @pytest.mark.parametrize("code", [101, 102, 103, 104, 105])
    def test_lookup_all_model_codes(self, code: int) -> None:
        error = lookup_error(code)
        assert error.category == ErrorCategory.model

    @pytest.mark.parametrize("code", [201, 202, 203, 204, 205])
    def test_lookup_all_tool_codes(self, code: int) -> None:
        error = lookup_error(code)
        assert error.category == ErrorCategory.tool


# ---------------------------------------------------------------------------
# errors_by_category tests
# ---------------------------------------------------------------------------


class TestErrorsByCategory:
    """Tests for the errors_by_category function."""

    def test_model_category_returns_list(self) -> None:
        result = errors_by_category(ErrorCategory.model)
        assert isinstance(result, list)

    def test_model_category_not_empty(self) -> None:
        result = errors_by_category(ErrorCategory.model)
        assert len(result) > 0

    def test_all_returned_errors_match_category(self) -> None:
        for cat in ErrorCategory:
            errors = errors_by_category(cat)
            for error in errors:
                assert error.category == cat

    def test_result_sorted_by_code(self) -> None:
        result = errors_by_category(ErrorCategory.model)
        codes = [e.code for e in result]
        assert codes == sorted(codes)

    def test_security_errors_sorted(self) -> None:
        result = errors_by_category(ErrorCategory.security)
        codes = [e.code for e in result]
        assert codes == sorted(codes)

    def test_security_errors_all_critical(self) -> None:
        result = errors_by_category(ErrorCategory.security)
        for error in result:
            assert error.severity == "critical"

    def test_all_categories_have_errors(self) -> None:
        for cat in ErrorCategory:
            assert len(errors_by_category(cat)) > 0

    def test_no_cross_category_contamination(self) -> None:
        model_errors = errors_by_category(ErrorCategory.model)
        tool_errors = errors_by_category(ErrorCategory.tool)
        model_codes = {e.code for e in model_errors}
        tool_codes = {e.code for e in tool_errors}
        assert model_codes.isdisjoint(tool_codes)


# ---------------------------------------------------------------------------
# classify_exception tests
# ---------------------------------------------------------------------------


class TestClassifyException:
    """Tests for the classify_exception function."""

    def test_timeout_error_maps_to_103(self) -> None:
        error = classify_exception(TimeoutError("timed out"))
        assert error.code == 103

    def test_connection_error_maps_to_404(self) -> None:
        error = classify_exception(ConnectionError("connection failed"))
        assert error.code == 404

    def test_permission_error_maps_to_302(self) -> None:
        error = classify_exception(PermissionError("denied"))
        assert error.code == 302

    def test_file_not_found_maps_to_602(self) -> None:
        error = classify_exception(FileNotFoundError("not found"))
        assert error.code == 602

    def test_memory_error_maps_to_401(self) -> None:
        error = classify_exception(MemoryError("out of memory"))
        assert error.code == 401

    def test_recursion_error_maps_to_501(self) -> None:
        error = classify_exception(RecursionError("max depth"))
        assert error.code == 501

    def test_value_error_maps_to_601(self) -> None:
        error = classify_exception(ValueError("bad value"))
        assert error.code == 601

    def test_key_error_maps_to_602(self) -> None:
        error = classify_exception(KeyError("missing key"))
        assert error.code == 602

    def test_type_error_maps_to_203(self) -> None:
        error = classify_exception(TypeError("wrong type"))
        assert error.code == 203

    def test_os_error_maps_to_405(self) -> None:
        error = classify_exception(OSError("disk error"))
        assert error.code == 405

    def test_unknown_exception_falls_back_to_601(self) -> None:
        class MyCustomException(Exception):
            pass
        error = classify_exception(MyCustomException("unknown"))
        assert error.code == 601

    def test_classify_returns_agent_error(self) -> None:
        error = classify_exception(ValueError("test"))
        assert isinstance(error, AgentError)

    def test_unicode_decode_error_maps_to_605(self) -> None:
        exc = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        error = classify_exception(exc)
        assert error.code == 605

    def test_socket_timeout_maps_to_103(self) -> None:
        error = classify_exception(socket.timeout("socket timed out"))
        assert error.code == 103

    def test_url_error_maps_to_404(self) -> None:
        error = classify_exception(urllib.error.URLError("url error"))
        assert error.code == 404

    def test_connection_refused_maps_to_404(self) -> None:
        error = classify_exception(ConnectionRefusedError("refused"))
        assert error.code == 404


# ---------------------------------------------------------------------------
# AgentErrorException tests
# ---------------------------------------------------------------------------


class TestAgentErrorException:
    """Tests for the AgentErrorException class."""

    def test_create_with_error(self) -> None:
        error = lookup_error(101)
        exc = AgentErrorException(error)
        assert exc.error is error

    def test_message_contains_code(self) -> None:
        error = lookup_error(101)
        exc = AgentErrorException(error)
        assert "101" in str(exc)

    def test_message_contains_name(self) -> None:
        error = lookup_error(101)
        exc = AgentErrorException(error)
        assert "model_not_found" in str(exc)

    def test_details_appended_to_message(self) -> None:
        error = lookup_error(201)
        exc = AgentErrorException(error, details="Tool 'search' not found")
        assert "Tool 'search' not found" in str(exc)

    def test_details_none_by_default(self) -> None:
        error = lookup_error(101)
        exc = AgentErrorException(error)
        assert exc.details is None

    def test_is_exception(self) -> None:
        error = lookup_error(101)
        exc = AgentErrorException(error)
        assert isinstance(exc, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        error = lookup_error(301)
        with pytest.raises(AgentErrorException) as exc_info:
            raise AgentErrorException(error, "auth failed")
        assert exc_info.value.error.code == 301

    def test_details_stored_correctly(self) -> None:
        error = lookup_error(501)
        exc = AgentErrorException(error, details="limit exceeded after 100 iterations")
        assert exc.details == "limit exceeded after 100 iterations"


# ---------------------------------------------------------------------------
# create_error_response tests
# ---------------------------------------------------------------------------


class TestCreateErrorResponse:
    """Tests for the create_error_response function."""

    def test_returns_dict(self) -> None:
        error = lookup_error(101)
        result = create_error_response(error)
        assert isinstance(result, dict)

    def test_has_error_key(self) -> None:
        error = lookup_error(101)
        result = create_error_response(error)
        assert "error" in result

    def test_error_dict_has_code(self) -> None:
        error = lookup_error(101)
        result = create_error_response(error)
        assert result["error"]["code"] == 101  # type: ignore[index]

    def test_error_dict_has_name(self) -> None:
        error = lookup_error(101)
        result = create_error_response(error)
        assert result["error"]["name"] == "model_not_found"  # type: ignore[index]

    def test_error_dict_has_category(self) -> None:
        error = lookup_error(101)
        result = create_error_response(error)
        assert result["error"]["category"] == "model"  # type: ignore[index]

    def test_error_dict_has_severity(self) -> None:
        error = lookup_error(101)
        result = create_error_response(error)
        assert "severity" in result["error"]  # type: ignore[index]

    def test_error_dict_has_retryable(self) -> None:
        error = lookup_error(101)
        result = create_error_response(error)
        assert "retryable" in result["error"]  # type: ignore[index]

    def test_error_dict_has_timestamp(self) -> None:
        error = lookup_error(101)
        result = create_error_response(error)
        assert "timestamp" in result["error"]  # type: ignore[index]

    def test_details_included_when_provided(self) -> None:
        error = lookup_error(201)
        result = create_error_response(error, details="search tool missing")
        assert result["error"]["details"] == "search tool missing"  # type: ignore[index]

    def test_details_none_when_not_provided(self) -> None:
        error = lookup_error(201)
        result = create_error_response(error)
        assert result["error"]["details"] is None  # type: ignore[index]

    def test_retryable_false_for_non_retryable(self) -> None:
        error = lookup_error(101)  # model_not_found is not retryable
        result = create_error_response(error)
        assert result["error"]["retryable"] is False  # type: ignore[index]

    def test_retryable_true_for_retryable(self) -> None:
        error = lookup_error(103)  # model_timeout is retryable
        result = create_error_response(error)
        assert result["error"]["retryable"] is True  # type: ignore[index]

    def test_timestamp_is_iso_format(self) -> None:
        error = lookup_error(101)
        result = create_error_response(error)
        timestamp = result["error"]["timestamp"]  # type: ignore[index]
        assert "T" in str(timestamp)  # ISO 8601 format contains 'T'


# ---------------------------------------------------------------------------
# AgentError model tests
# ---------------------------------------------------------------------------


class TestAgentErrorModel:
    """Tests for the AgentError Pydantic model."""

    def test_create_valid_error(self) -> None:
        error = AgentError(
            code=999,
            category=ErrorCategory.model,
            name="test_error",
            description="A test error",
            retryable=False,
            severity="high",
        )
        assert error.code == 999

    def test_invalid_severity_raises(self) -> None:
        with pytest.raises(Exception):
            AgentError(
                code=999,
                category=ErrorCategory.model,
                name="test_error",
                description="A test",
                retryable=False,
                severity="ultra",
            )

    def test_negative_code_raises(self) -> None:
        with pytest.raises(Exception):
            AgentError(
                code=-1,
                category=ErrorCategory.model,
                name="test_error",
                description="A test",
                retryable=False,
                severity="high",
            )

    def test_zero_code_raises(self) -> None:
        with pytest.raises(Exception):
            AgentError(
                code=0,
                category=ErrorCategory.model,
                name="test_error",
                description="A test",
                retryable=False,
                severity="high",
            )

    @pytest.mark.parametrize("severity", ["critical", "high", "medium", "low"])
    def test_all_valid_severities(self, severity: str) -> None:
        error = AgentError(
            code=1,
            category=ErrorCategory.tool,
            name="test",
            description="test",
            retryable=False,
            severity=severity,
        )
        assert error.severity == severity


class TestErrorCategory:
    """Tests for the ErrorCategory enum."""

    def test_all_categories_exist(self) -> None:
        categories = [c.value for c in ErrorCategory]
        assert "model" in categories
        assert "tool" in categories
        assert "security" in categories
        assert "resource" in categories
        assert "orchestration" in categories
        assert "data" in categories

    def test_category_is_string_enum(self) -> None:
        assert isinstance(ErrorCategory.model, str)


class TestErrorRegistryModel:
    """Tests for the ErrorRegistry Pydantic model."""

    def test_create_empty_registry(self) -> None:
        registry = ErrorRegistry()
        assert registry.errors == {}

    def test_register_error(self) -> None:
        registry = ErrorRegistry()
        error = AgentError(
            code=999,
            category=ErrorCategory.model,
            name="test",
            description="test",
            retryable=False,
            severity="low",
        )
        registry.register(error)
        assert 999 in registry.errors

    def test_get_existing_error(self) -> None:
        registry = ErrorRegistry()
        error = AgentError(
            code=999,
            category=ErrorCategory.model,
            name="test",
            description="test",
            retryable=False,
            severity="low",
        )
        registry.register(error)
        result = registry.get(999)
        assert result is error

    def test_get_nonexistent_returns_none(self) -> None:
        registry = ErrorRegistry()
        assert registry.get(9999) is None

    def test_by_category_returns_matching(self) -> None:
        registry = ErrorRegistry()
        error = AgentError(
            code=999,
            category=ErrorCategory.model,
            name="test",
            description="test",
            retryable=False,
            severity="low",
        )
        registry.register(error)
        result = registry.by_category(ErrorCategory.model)
        assert error in result

    def test_by_category_excludes_other_categories(self) -> None:
        registry = ErrorRegistry()
        error = AgentError(
            code=999,
            category=ErrorCategory.tool,
            name="test",
            description="test",
            retryable=False,
            severity="low",
        )
        registry.register(error)
        result = registry.by_category(ErrorCategory.model)
        assert error not in result

    def test_register_replaces_existing(self) -> None:
        registry = ErrorRegistry()
        error1 = AgentError(
            code=999,
            category=ErrorCategory.model,
            name="first",
            description="first",
            retryable=False,
            severity="low",
        )
        error2 = AgentError(
            code=999,
            category=ErrorCategory.model,
            name="second",
            description="second",
            retryable=True,
            severity="high",
        )
        registry.register(error1)
        registry.register(error2)
        assert registry.get(999).name == "second"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Hypothesis-based property tests
# ---------------------------------------------------------------------------


@given(code=st.integers(min_value=100, max_value=999))
@settings(max_examples=30)
def test_lookup_known_codes_never_raises_internal_error(code: int) -> None:
    """Calling lookup_error on any code either returns an error or raises UnknownErrorCode."""
    try:
        result = lookup_error(code)
        assert isinstance(result, AgentError)
    except UnknownErrorCode:
        pass  # Expected for codes not in the registry


@given(code=st.integers(max_value=0))
@settings(max_examples=20)
def test_lookup_non_positive_codes_always_raise(code: int) -> None:
    """Codes <= 0 are never in the registry."""
    with pytest.raises(UnknownErrorCode):
        lookup_error(code)

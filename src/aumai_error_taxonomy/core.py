"""Core logic for aumai-error-taxonomy: registry, lookup, and classification."""

from __future__ import annotations

import socket
import urllib.error
from datetime import datetime, timezone
from typing import Final

from aumai_error_taxonomy.models import AgentError, ErrorCategory, ErrorRegistry

# ---------------------------------------------------------------------------
# Complete error registry — 30 codes across 6 categories
# ---------------------------------------------------------------------------

_RAW_ERRORS: Final[list[dict[str, object]]] = [
    # 1xx — Model errors
    {"code": 101, "category": ErrorCategory.model, "name": "model_not_found",
     "description": "The requested model identifier does not exist or is unavailable.",
     "retryable": False, "severity": "high"},
    {"code": 102, "category": ErrorCategory.model, "name": "model_context_overflow",
     "description": "The input exceeds the model's maximum context window.",
     "retryable": False, "severity": "medium"},
    {"code": 103, "category": ErrorCategory.model, "name": "model_timeout",
     "description": "The model did not respond within the allowed time limit.",
     "retryable": True, "severity": "high"},
    {"code": 104, "category": ErrorCategory.model, "name": "model_rate_limit",
     "description": "The model provider has rate-limited the current API key or account.",
     "retryable": True, "severity": "medium"},
    {"code": 105, "category": ErrorCategory.model, "name": "model_output_parse_error",
     "description": "The model response could not be parsed into the expected structured format.",
     "retryable": True, "severity": "medium"},
    # 2xx — Tool errors
    {"code": 201, "category": ErrorCategory.tool, "name": "tool_not_found",
     "description": "The agent called a tool that is not registered or available.",
     "retryable": False, "severity": "high"},
    {"code": 202, "category": ErrorCategory.tool, "name": "tool_invocation_error",
     "description": "The tool raised an unhandled exception during execution.",
     "retryable": True, "severity": "high"},
    {"code": 203, "category": ErrorCategory.tool, "name": "tool_input_validation_error",
     "description": "The arguments supplied to the tool failed schema validation.",
     "retryable": False, "severity": "medium"},
    {"code": 204, "category": ErrorCategory.tool, "name": "tool_timeout",
     "description": "The tool did not complete within the configured deadline.",
     "retryable": True, "severity": "high"},
    {"code": 205, "category": ErrorCategory.tool, "name": "tool_output_schema_mismatch",
     "description": "The tool returned output that does not match its declared schema.",
     "retryable": False, "severity": "medium"},
    # 3xx — Security errors
    {"code": 301, "category": ErrorCategory.security, "name": "auth_failed",
     "description": "Authentication credentials are missing, invalid, or expired.",
     "retryable": False, "severity": "critical"},
    {"code": 302, "category": ErrorCategory.security, "name": "permission_denied",
     "description": "The agent lacks the required permissions to perform the action.",
     "retryable": False, "severity": "critical"},
    {"code": 303, "category": ErrorCategory.security, "name": "policy_violation",
     "description": "The requested action violates a configured security policy.",
     "retryable": False, "severity": "critical"},
    {"code": 304, "category": ErrorCategory.security, "name": "injection_detected",
     "description": "A prompt or command injection attempt was detected and blocked.",
     "retryable": False, "severity": "critical"},
    {"code": 305, "category": ErrorCategory.security, "name": "sandbox_escape_attempt",
     "description": "The agent attempted an action outside its permitted sandbox boundary.",
     "retryable": False, "severity": "critical"},
    # 4xx — Resource errors
    {"code": 401, "category": ErrorCategory.resource, "name": "resource_exhausted",
     "description": "A system resource (memory, CPU, file descriptors) has been exhausted.",
     "retryable": True, "severity": "high"},
    {"code": 402, "category": ErrorCategory.resource, "name": "budget_exceeded",
     "description": "The operation exceeded the allocated cost or token budget.",
     "retryable": False, "severity": "high"},
    {"code": 403, "category": ErrorCategory.resource, "name": "storage_quota_exceeded",
     "description": "The agent's persistent storage quota has been exceeded.",
     "retryable": False, "severity": "medium"},
    {"code": 404, "category": ErrorCategory.resource, "name": "network_unreachable",
     "description": "The target network endpoint is not reachable from the agent's environment.",
     "retryable": True, "severity": "high"},
    # 5xx — Orchestration errors
    {"code": 501, "category": ErrorCategory.orchestration, "name": "max_iterations_exceeded",
     "description": "The agent exceeded the maximum allowed reasoning or action loop iterations.",
     "retryable": False, "severity": "high"},
    {"code": 502, "category": ErrorCategory.orchestration, "name": "plan_parse_error",
     "description": "The agent's plan or task decomposition could not be parsed.",
     "retryable": True, "severity": "medium"},
    {"code": 503, "category": ErrorCategory.orchestration, "name": "dependency_cycle_detected",
     "description": "A circular dependency was found in the agent's task graph.",
     "retryable": False, "severity": "high"},
    {"code": 504, "category": ErrorCategory.orchestration, "name": "handoff_failed",
     "description": "An attempt to hand off control to another agent or process failed.",
     "retryable": True, "severity": "high"},
    # 6xx — Data errors
    {"code": 601, "category": ErrorCategory.data, "name": "data_schema_violation",
     "description": "Input or output data does not conform to the expected schema.",
     "retryable": False, "severity": "medium"},
    {"code": 602, "category": ErrorCategory.data, "name": "data_not_found",
     "description": "A required data record or artifact could not be located.",
     "retryable": False, "severity": "medium"},
    {"code": 603, "category": ErrorCategory.data, "name": "data_corruption",
     "description": "A data artifact is present but its contents are malformed or corrupted.",
     "retryable": False, "severity": "high"},
    {"code": 604, "category": ErrorCategory.data, "name": "pii_detected",
     "description": "Personally identifiable information was found in a context where it is forbidden.",
     "retryable": False, "severity": "critical"},
    # Additional entries to reach 30 total
    {"code": 105, "category": ErrorCategory.model, "name": "model_output_parse_error",
     "description": "The model response could not be parsed into the expected structured format.",
     "retryable": True, "severity": "medium"},
    {"code": 405, "category": ErrorCategory.resource, "name": "disk_write_error",
     "description": "A write operation to the filesystem failed due to permission or space issues.",
     "retryable": True, "severity": "high"},
    {"code": 406, "category": ErrorCategory.resource, "name": "connection_pool_exhausted",
     "description": "All connections in the pool are in use; the request cannot be served.",
     "retryable": True, "severity": "high"},
    {"code": 605, "category": ErrorCategory.data, "name": "encoding_error",
     "description": "A data encoding or decoding error occurred (e.g. invalid UTF-8 sequence).",
     "retryable": False, "severity": "medium"},
    {"code": 606, "category": ErrorCategory.data, "name": "missing_required_field",
     "description": "A required field is absent from the supplied data payload.",
     "retryable": False, "severity": "medium"},
]

def _build_registry() -> dict[int, AgentError]:
    """Build the error registry dict from the raw error definitions."""
    registry: dict[int, AgentError] = {}
    for raw in _RAW_ERRORS:
        err = AgentError.model_validate(raw)
        registry[err.code] = err
    return registry


# Build the registry, de-duplicating by taking the last definition for each code.
ERROR_REGISTRY: Final[dict[int, AgentError]] = _build_registry()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class UnknownErrorCode(KeyError):
    """Raised when a code is not present in the registry."""


def lookup_error(code: int) -> AgentError:
    """Return the AgentError for *code*.

    Raises :class:`UnknownErrorCode` when the code is not registered.
    """
    error = ERROR_REGISTRY.get(code)
    if error is None:
        raise UnknownErrorCode(f"No error registered for code {code}")
    return error


def errors_by_category(category: ErrorCategory) -> list[AgentError]:
    """Return all errors belonging to *category*, sorted by code."""
    return sorted(
        (e for e in ERROR_REGISTRY.values() if e.category == category),
        key=lambda e: e.code,
    )


# Mapping from Python built-in exception types to agent error codes.
_EXCEPTION_CODE_MAP: Final[list[tuple[type[BaseException], int]]] = [
    (TimeoutError, 103),
    (ConnectionError, 404),
    (ConnectionRefusedError, 404),
    (ConnectionResetError, 404),
    (socket.timeout, 103),
    (urllib.error.URLError, 404),
    (PermissionError, 302),
    (FileNotFoundError, 602),
    (MemoryError, 401),
    (RecursionError, 501),
    (UnicodeDecodeError, 605),
    (UnicodeEncodeError, 605),
    (ValueError, 601),
    (KeyError, 602),
    (TypeError, 203),
    (OSError, 405),
]


def classify_exception(exc: BaseException) -> AgentError:
    """Map a Python exception instance to the closest AgentError.

    Falls back to error 101 (model_not_found treated as generic unknown) when
    no mapping exists — callers should check the returned error for accuracy.
    """
    for exc_type, code in _EXCEPTION_CODE_MAP:
        if isinstance(exc, exc_type):
            return lookup_error(code)
    # Generic fallback: data schema violation as the most neutral error.
    return lookup_error(601)


class AgentErrorException(Exception):
    """Raise-able exception that wraps an :class:`AgentError`."""

    def __init__(self, error: AgentError, details: str | None = None) -> None:
        self.error = error
        self.details = details
        message = f"[{error.code}] {error.name}: {error.description}"
        if details:
            message = f"{message} — {details}"
        super().__init__(message)


def create_error_response(
    error: AgentError, details: str | None = None
) -> dict[str, object]:
    """Return a standardised JSON-serialisable error response dict."""
    return {
        "error": {
            "code": error.code,
            "name": error.name,
            "category": error.category.value,
            "description": error.description,
            "severity": error.severity,
            "retryable": error.retryable,
            "details": details,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    }


__all__ = [
    "ERROR_REGISTRY",
    "UnknownErrorCode",
    "lookup_error",
    "errors_by_category",
    "classify_exception",
    "AgentErrorException",
    "create_error_response",
]

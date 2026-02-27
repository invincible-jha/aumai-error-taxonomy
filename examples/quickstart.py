"""Quickstart examples for aumai-error-taxonomy.

Demonstrates the five main use cases:
  1. Looking up error codes from the built-in registry
  2. Browsing errors by category
  3. Classifying Python exceptions to agent errors
  4. Building structured error responses
  5. Raising and catching AgentErrorException

Run this file directly to see all demos:

    python examples/quickstart.py
"""

from __future__ import annotations

import json

from aumai_error_taxonomy import (
    ERROR_REGISTRY,
    AgentError,
    AgentErrorException,
    ErrorCategory,
    ErrorRegistry,
    UnknownErrorCode,
    classify_exception,
    create_error_response,
    errors_by_category,
    lookup_error,
)


def demo_lookup() -> None:
    """Demo 1: Look up error codes from the built-in registry.

    ERROR_REGISTRY is a dict[int, AgentError] built at import time.
    lookup_error() is a direct O(1) dict lookup.
    """
    print("=" * 60)
    print("DEMO 1 — Error code lookup")
    print("=" * 60)

    # Look up a few representative codes
    codes_to_show = [103, 304, 501, 604]
    for code in codes_to_show:
        error = lookup_error(code)
        retry_label = "retryable" if error.retryable else "no-retry"
        print(
            f"  [{error.code:3d}] {error.name:<35s} "
            f"sev={error.severity:<10s} {retry_label}"
        )

    # Show total registry size
    print(f"\nTotal errors in registry: {len(ERROR_REGISTRY)}")

    # Demonstrate UnknownErrorCode
    try:
        lookup_error(9999)
    except UnknownErrorCode as exc:
        print(f"Unknown code 9999 -> UnknownErrorCode raised: {exc}")
    print()


def demo_browse_by_category() -> None:
    """Demo 2: Browse all errors in a category.

    errors_by_category() returns AgentError objects sorted by code.
    """
    print("=" * 60)
    print("DEMO 2 — Browse errors by category")
    print("=" * 60)

    # Show a summary count per category
    for category in ErrorCategory:
        errors = errors_by_category(category)
        retryable = sum(1 for e in errors if e.retryable)
        print(
            f"  {category.value:<15s}: {len(errors):2d} codes, "
            f"{retryable} retryable"
        )

    # Show security errors in detail (all critical, all non-retryable)
    print("\nSecurity errors (full detail):")
    for error in errors_by_category(ErrorCategory.security):
        print(f"  [{error.code}] {error.name}")
        print(f"       {error.description}")
    print()


def demo_classify_exceptions() -> None:
    """Demo 3: Map Python exceptions to agent error codes.

    classify_exception() walks an ordered isinstance() map.
    Subclasses are matched before parent classes.
    Falls back to error 601 for unknown exceptions.
    """
    print("=" * 60)
    print("DEMO 3 — Exception classification")
    print("=" * 60)

    # A selection of Python built-in exceptions to classify
    test_exceptions: list[BaseException] = [
        TimeoutError("model did not respond"),
        ConnectionRefusedError("refused on port 443"),
        ConnectionResetError("connection reset by peer"),
        ConnectionError("generic connection failure"),
        PermissionError("access denied to /etc/secret"),
        FileNotFoundError("no such file: /data/model.bin"),
        MemoryError("unable to allocate 4GB"),
        RecursionError("maximum recursion depth exceeded"),
        UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1, "invalid byte"),
        ValueError("expected int, got str"),
        KeyError("missing_key"),
        TypeError("argument of type int is not iterable"),
        OSError("write error: disk full"),
        RuntimeError("completely unknown error"),  # falls back to 601
    ]

    print(f"  {'Exception type':<35s} -> Code  Name")
    print("  " + "-" * 65)
    for exc in test_exceptions:
        error = classify_exception(exc)
        print(
            f"  {type(exc).__name__:<35s} -> "
            f"[{error.code:3d}] {error.name}"
        )
    print()


def demo_structured_response() -> None:
    """Demo 4: Build structured JSON error responses.

    create_error_response() produces a JSON-safe dict with a UTC
    timestamp. Use this in API handlers and observability pipelines.
    """
    print("=" * 60)
    print("DEMO 4 — Structured error responses")
    print("=" * 60)

    # Simulate an exception in agent code
    try:
        raise TimeoutError("No model response after 30 seconds")
    except TimeoutError as exc:
        agent_error = classify_exception(exc)
        response = create_error_response(agent_error, details=str(exc))

    print("Structured response (JSON):")
    print(json.dumps(response, indent=2))

    # Show how to use retryable flag in a controller
    error_data = response["error"]
    if error_data["retryable"]:  # type: ignore[index]
        print(f"\nThis error is retryable — schedule a retry.")
    else:
        print(f"\nThis error is not retryable — alert the on-call engineer.")
    print()


def demo_agent_error_exception() -> None:
    """Demo 5: Raise and catch AgentErrorException.

    AgentErrorException wraps an AgentError into a standard Python
    exception. Callers can inspect .error and .details directly.
    """
    print("=" * 60)
    print("DEMO 5 — AgentErrorException")
    print("=" * 60)

    def process_data(payload: dict[str, object]) -> str:
        """Simulate agent data processing with structured error raising."""
        if "id" not in payload:
            raise AgentErrorException(
                lookup_error(606),  # missing_required_field
                details="Field 'id' is required in the data payload",
            )
        if len(str(payload.get("text", ""))) > 10_000:
            raise AgentErrorException(
                lookup_error(102),  # model_context_overflow
                details="Text field exceeds 10,000 character limit",
            )
        return f"Processed record {payload['id']}"

    # Case A: successful call
    try:
        result = process_data({"id": "order-123", "text": "Refund request"})
        print(f"Case A (success): {result}")
    except AgentErrorException as exc:
        print(f"Case A failed: {exc}")

    # Case B: missing field
    try:
        process_data({"text": "No id present"})
    except AgentErrorException as exc:
        print(f"\nCase B (missing field):")
        print(f"  Error code : {exc.error.code}")
        print(f"  Error name : {exc.error.name}")
        print(f"  Severity   : {exc.error.severity}")
        print(f"  Retryable  : {exc.error.retryable}")
        print(f"  Details    : {exc.details}")
        print(f"  str(exc)   : {exc}")

    print()


def demo_custom_registry() -> None:
    """Demo 6: Build a custom ErrorRegistry for application-specific codes.

    The built-in ERROR_REGISTRY uses codes 101-606.
    Application codes can use 7xx+ to avoid collisions.
    """
    print("=" * 60)
    print("DEMO 6 — Custom ErrorRegistry")
    print("=" * 60)

    # Build a small application-specific registry
    app_registry = ErrorRegistry()
    app_registry.register(AgentError(
        code=701,
        category=ErrorCategory.data,
        name="invalid_order_state",
        description="The order is in a state that does not permit this operation.",
        retryable=False,
        severity="medium",
    ))
    app_registry.register(AgentError(
        code=702,
        category=ErrorCategory.orchestration,
        name="agent_handoff_quota_exceeded",
        description="The maximum number of agent-to-agent handoffs has been reached.",
        retryable=False,
        severity="high",
    ))

    # Lookup from custom registry
    error = app_registry.get(701)
    print(f"Custom code 701: {error.name if error else 'not found'}")

    # Filter by category
    orchestration_errors = app_registry.by_category(ErrorCategory.orchestration)
    print(f"Custom orchestration errors: {len(orchestration_errors)}")
    for err in orchestration_errors:
        print(f"  [{err.code}] {err.name}")
    print()


def main() -> None:
    """Run all demos in sequence."""
    demo_lookup()
    demo_browse_by_category()
    demo_classify_exceptions()
    demo_structured_response()
    demo_agent_error_exception()
    demo_custom_registry()

    print("All demos complete.")


if __name__ == "__main__":
    main()

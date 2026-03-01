"""Tests for aumai_error_taxonomy.async_core — AsyncErrorRegistry."""

from __future__ import annotations

import pytest

from aumai_async_core import AsyncServiceConfig

from aumai_error_taxonomy.async_core import AsyncErrorRegistry
from aumai_error_taxonomy.core import ERROR_REGISTRY, UnknownErrorCode
from aumai_error_taxonomy.models import AgentError, ErrorCategory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def registry() -> AsyncErrorRegistry:
    """Return a started AsyncErrorRegistry for use in tests."""
    config = AsyncServiceConfig(
        name="test-error-registry",
        health_check_interval_seconds=0.0,
    )
    reg = AsyncErrorRegistry(config)
    await reg.start()
    yield reg
    await reg.stop()


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------


class TestAsyncErrorRegistryLifecycle:
    async def test_start_transitions_to_running(self) -> None:
        reg = AsyncErrorRegistry()
        await reg.start()
        assert reg.status.state == "running"
        await reg.stop()

    async def test_stop_transitions_to_stopped(self) -> None:
        reg = AsyncErrorRegistry()
        await reg.start()
        await reg.stop()
        assert reg.status.state == "stopped"

    async def test_context_manager_starts_and_stops(self) -> None:
        config = AsyncServiceConfig(
            name="ctx-test", health_check_interval_seconds=0.0
        )
        async with AsyncErrorRegistry(config) as reg:
            assert reg.status.state == "running"

    async def test_default_config_name(self) -> None:
        reg = AsyncErrorRegistry()
        assert reg.config.name == "aumai-error-taxonomy"

    async def test_custom_config_name(self) -> None:
        config = AsyncServiceConfig(
            name="custom-registry", health_check_interval_seconds=0.0
        )
        reg = AsyncErrorRegistry(config)
        assert reg.config.name == "custom-registry"

    async def test_health_check_returns_true(self, registry: AsyncErrorRegistry) -> None:
        result = await registry.health_check()
        assert result is True

    async def test_status_has_name(self, registry: AsyncErrorRegistry) -> None:
        assert registry.status.name == "test-error-registry"

    async def test_emitter_is_accessible(self, registry: AsyncErrorRegistry) -> None:
        assert registry.emitter is not None


# ---------------------------------------------------------------------------
# lookup_error tests
# ---------------------------------------------------------------------------


class TestAsyncLookupError:
    async def test_lookup_known_code_returns_agent_error(
        self, registry: AsyncErrorRegistry
    ) -> None:
        error = await registry.lookup_error(101)
        assert isinstance(error, AgentError)

    async def test_lookup_returns_correct_code(
        self, registry: AsyncErrorRegistry
    ) -> None:
        error = await registry.lookup_error(101)
        assert error.code == 101

    async def test_lookup_returns_correct_name(
        self, registry: AsyncErrorRegistry
    ) -> None:
        error = await registry.lookup_error(101)
        assert error.name == "model_not_found"

    async def test_lookup_unknown_code_raises_unknown_error_code(
        self, registry: AsyncErrorRegistry
    ) -> None:
        with pytest.raises(UnknownErrorCode):
            await registry.lookup_error(9999)

    async def test_lookup_increments_request_count(
        self, registry: AsyncErrorRegistry
    ) -> None:
        initial = registry.status.request_count
        await registry.lookup_error(101)
        assert registry.status.request_count == initial + 1

    async def test_lookup_failure_increments_error_count(
        self, registry: AsyncErrorRegistry
    ) -> None:
        initial = registry.status.error_count
        with pytest.raises(UnknownErrorCode):
            await registry.lookup_error(9999)
        assert registry.status.error_count == initial + 1

    async def test_lookup_emits_looked_up_event(
        self, registry: AsyncErrorRegistry
    ) -> None:
        received: list[dict] = []

        async def handler(**kwargs: object) -> None:
            received.append(dict(kwargs))

        registry.emitter.on("error.looked_up", handler)
        await registry.lookup_error(101)
        assert len(received) == 1
        assert received[0]["error_code"] == 101
        assert received[0]["error_name"] == "model_not_found"

    async def test_lookup_failure_emits_lookup_failed_event(
        self, registry: AsyncErrorRegistry
    ) -> None:
        received: list[dict] = []

        async def handler(**kwargs: object) -> None:
            received.append(dict(kwargs))

        registry.emitter.on("error.lookup_failed", handler)
        with pytest.raises(UnknownErrorCode):
            await registry.lookup_error(9999)
        assert len(received) == 1
        assert received[0]["error_code"] == 9999

    @pytest.mark.parametrize("code", [101, 201, 301, 401, 501, 601])
    async def test_lookup_all_category_roots(
        self, registry: AsyncErrorRegistry, code: int
    ) -> None:
        error = await registry.lookup_error(code)
        assert error.code == code


# ---------------------------------------------------------------------------
# classify_exception tests
# ---------------------------------------------------------------------------


class TestAsyncClassifyException:
    async def test_classify_timeout_error(
        self, registry: AsyncErrorRegistry
    ) -> None:
        error = await registry.classify_exception(TimeoutError("timeout"))
        assert error.code == 103

    async def test_classify_permission_error(
        self, registry: AsyncErrorRegistry
    ) -> None:
        error = await registry.classify_exception(PermissionError("denied"))
        assert error.code == 302

    async def test_classify_value_error(
        self, registry: AsyncErrorRegistry
    ) -> None:
        error = await registry.classify_exception(ValueError("bad value"))
        assert error.code == 601

    async def test_classify_file_not_found(
        self, registry: AsyncErrorRegistry
    ) -> None:
        error = await registry.classify_exception(FileNotFoundError("missing"))
        assert error.code == 602

    async def test_classify_memory_error(
        self, registry: AsyncErrorRegistry
    ) -> None:
        error = await registry.classify_exception(MemoryError("oom"))
        assert error.code == 401

    async def test_classify_returns_agent_error(
        self, registry: AsyncErrorRegistry
    ) -> None:
        error = await registry.classify_exception(TypeError("type mismatch"))
        assert isinstance(error, AgentError)

    async def test_classify_increments_request_count(
        self, registry: AsyncErrorRegistry
    ) -> None:
        initial = registry.status.request_count
        await registry.classify_exception(ValueError("test"))
        assert registry.status.request_count == initial + 1

    async def test_classify_emits_error_classified_event(
        self, registry: AsyncErrorRegistry
    ) -> None:
        received: list[dict] = []

        async def handler(**kwargs: object) -> None:
            received.append(dict(kwargs))

        registry.emitter.on("error.classified", handler)
        await registry.classify_exception(TimeoutError("test"))
        assert len(received) == 1
        event = received[0]
        assert event["error_code"] == 103
        assert event["error_name"] == "model_timeout"
        assert event["category"] == "model"
        assert event["retryable"] is True
        assert event["severity"] == "high"

    async def test_classify_unknown_exception_falls_back_to_601(
        self, registry: AsyncErrorRegistry
    ) -> None:
        class UnknownError(Exception):
            pass

        error = await registry.classify_exception(UnknownError("custom"))
        assert error.code == 601

    async def test_classify_emits_event_for_unknown_exception(
        self, registry: AsyncErrorRegistry
    ) -> None:
        received: list[dict] = []

        async def handler(**kwargs: object) -> None:
            received.append(dict(kwargs))

        registry.emitter.on("error.classified", handler)

        class SomeUnknownError(Exception):
            pass

        await registry.classify_exception(SomeUnknownError("x"))
        assert len(received) == 1


# ---------------------------------------------------------------------------
# errors_by_category tests
# ---------------------------------------------------------------------------


class TestAsyncErrorsByCategory:
    async def test_returns_list_for_model_category(
        self, registry: AsyncErrorRegistry
    ) -> None:
        result = await registry.errors_by_category(ErrorCategory.model)
        assert isinstance(result, list)

    async def test_all_returned_errors_match_category(
        self, registry: AsyncErrorRegistry
    ) -> None:
        for cat in ErrorCategory:
            errors = await registry.errors_by_category(cat)
            for error in errors:
                assert error.category == cat

    async def test_result_is_sorted_by_code(
        self, registry: AsyncErrorRegistry
    ) -> None:
        result = await registry.errors_by_category(ErrorCategory.model)
        codes = [e.code for e in result]
        assert codes == sorted(codes)

    async def test_all_categories_have_errors(
        self, registry: AsyncErrorRegistry
    ) -> None:
        for cat in ErrorCategory:
            result = await registry.errors_by_category(cat)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# create_error_response tests
# ---------------------------------------------------------------------------


class TestAsyncCreateErrorResponse:
    async def test_returns_dict(self, registry: AsyncErrorRegistry) -> None:
        error = ERROR_REGISTRY[101]
        result = await registry.create_error_response(error)
        assert isinstance(result, dict)

    async def test_has_error_key(self, registry: AsyncErrorRegistry) -> None:
        error = ERROR_REGISTRY[101]
        result = await registry.create_error_response(error)
        assert "error" in result

    async def test_code_matches(self, registry: AsyncErrorRegistry) -> None:
        error = ERROR_REGISTRY[201]
        result = await registry.create_error_response(error)
        assert result["error"]["code"] == 201  # type: ignore[index]

    async def test_details_included(self, registry: AsyncErrorRegistry) -> None:
        error = ERROR_REGISTRY[101]
        result = await registry.create_error_response(error, details="extra info")
        assert result["error"]["details"] == "extra info"  # type: ignore[index]


# ---------------------------------------------------------------------------
# list_all_errors and registry_size tests
# ---------------------------------------------------------------------------


class TestAsyncRegistryHelpers:
    async def test_list_all_errors_returns_list(
        self, registry: AsyncErrorRegistry
    ) -> None:
        result = await registry.list_all_errors()
        assert isinstance(result, list)

    async def test_list_all_errors_sorted_by_code(
        self, registry: AsyncErrorRegistry
    ) -> None:
        result = await registry.list_all_errors()
        codes = [e.code for e in result]
        assert codes == sorted(codes)

    async def test_list_all_errors_non_empty(
        self, registry: AsyncErrorRegistry
    ) -> None:
        result = await registry.list_all_errors()
        assert len(result) > 0

    async def test_registry_size_positive(
        self, registry: AsyncErrorRegistry
    ) -> None:
        size = await registry.registry_size()
        assert size > 0

    async def test_registry_size_matches_error_registry(
        self, registry: AsyncErrorRegistry
    ) -> None:
        size = await registry.registry_size()
        assert size == len(ERROR_REGISTRY)


# ---------------------------------------------------------------------------
# Event emitter integration tests
# ---------------------------------------------------------------------------


class TestAsyncEventEmitter:
    async def test_multiple_listeners_all_called(
        self, registry: AsyncErrorRegistry
    ) -> None:
        calls: list[int] = []

        async def handler_a(**kwargs: object) -> None:
            calls.append(1)

        async def handler_b(**kwargs: object) -> None:
            calls.append(2)

        registry.emitter.on("error.classified", handler_a)
        registry.emitter.on("error.classified", handler_b)
        await registry.classify_exception(ValueError("test"))
        assert 1 in calls
        assert 2 in calls

    async def test_listener_count_after_registration(
        self, registry: AsyncErrorRegistry
    ) -> None:
        async def handler(**kwargs: object) -> None:
            pass

        registry.emitter.on("error.classified", handler)
        assert registry.emitter.listener_count("error.classified") >= 1

    async def test_once_handler_fires_only_once(
        self, registry: AsyncErrorRegistry
    ) -> None:
        call_count = 0

        async def handler(**kwargs: object) -> None:
            nonlocal call_count
            call_count += 1

        registry.emitter.once("error.classified", handler)
        await registry.classify_exception(ValueError("first"))
        await registry.classify_exception(ValueError("second"))
        assert call_count == 1

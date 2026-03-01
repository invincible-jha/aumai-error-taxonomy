"""Tests for aumai_error_taxonomy.store — ErrorStore and ErrorOccurrence."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aumai_store import Store

from aumai_error_taxonomy.models import AgentError, ErrorCategory
from aumai_error_taxonomy.store import ErrorOccurrence, ErrorStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def store() -> ErrorStore:
    """Return an in-memory ErrorStore ready for use."""
    error_store = await ErrorStore.create()
    yield error_store
    await error_store.close()


@pytest.fixture()
def sample_error() -> AgentError:
    """Return a sample AgentError for use in tests."""
    return AgentError(
        code=103,
        category=ErrorCategory.model,
        name="model_timeout",
        description="Model timed out.",
        retryable=True,
        severity="high",
    )


# ---------------------------------------------------------------------------
# ErrorOccurrence model tests
# ---------------------------------------------------------------------------


class TestErrorOccurrenceModel:
    def test_auto_generates_id(self) -> None:
        occ = ErrorOccurrence(error_code=101)
        assert len(occ.id) > 0

    def test_auto_generates_timestamp(self) -> None:
        occ = ErrorOccurrence(error_code=101)
        assert len(occ.timestamp) > 0

    def test_timestamp_is_iso_format(self) -> None:
        occ = ErrorOccurrence(error_code=101)
        assert "T" in occ.timestamp

    def test_default_agent_id_is_empty(self) -> None:
        occ = ErrorOccurrence(error_code=101)
        assert occ.agent_id == ""

    def test_default_context_is_empty(self) -> None:
        occ = ErrorOccurrence(error_code=101)
        assert occ.context == ""

    def test_default_stack_trace_is_empty(self) -> None:
        occ = ErrorOccurrence(error_code=101)
        assert occ.stack_trace == ""

    def test_explicit_fields_stored(self) -> None:
        occ = ErrorOccurrence(
            error_code=202,
            agent_id="agent-1",
            context="tool failed",
            stack_trace="Traceback...",
        )
        assert occ.error_code == 202
        assert occ.agent_id == "agent-1"
        assert occ.context == "tool failed"
        assert occ.stack_trace == "Traceback..."

    def test_unique_ids_per_instance(self) -> None:
        occ_a = ErrorOccurrence(error_code=101)
        occ_b = ErrorOccurrence(error_code=101)
        assert occ_a.id != occ_b.id


# ---------------------------------------------------------------------------
# ErrorStore.create tests
# ---------------------------------------------------------------------------


class TestErrorStoreCreate:
    async def test_create_returns_error_store(self) -> None:
        store = await ErrorStore.create()
        assert isinstance(store, ErrorStore)
        await store.close()

    async def test_create_with_explicit_store(self) -> None:
        memory_store = Store.memory()
        await memory_store.initialize()
        error_store = await ErrorStore.create(store=memory_store)
        assert isinstance(error_store, ErrorStore)
        await error_store.close()

    async def test_repository_is_accessible_after_create(self) -> None:
        error_store = await ErrorStore.create()
        assert error_store.repository is not None
        await error_store.close()

    async def test_context_manager_usage(self) -> None:
        error_store = await ErrorStore.create()
        async with error_store:
            result = await error_store.total_count()
            assert result == 0

    async def test_not_ready_before_create_raises(self) -> None:
        memory_store = Store.memory()
        raw = ErrorStore(memory_store)
        with pytest.raises(RuntimeError, match="not been initialised"):
            raw._ensure_ready()


# ---------------------------------------------------------------------------
# record_error tests
# ---------------------------------------------------------------------------


class TestRecordError:
    async def test_record_returns_string_id(self, store: ErrorStore) -> None:
        occurrence_id = await store.record_error(error_code=101)
        assert isinstance(occurrence_id, str)
        assert len(occurrence_id) > 0

    async def test_recorded_error_is_retrievable(self, store: ErrorStore) -> None:
        occurrence_id = await store.record_error(error_code=101)
        occ = await store.get_occurrence(occurrence_id)
        assert occ is not None
        assert occ.error_code == 101

    async def test_record_stores_agent_id(self, store: ErrorStore) -> None:
        occurrence_id = await store.record_error(error_code=101, agent_id="agent-x")
        occ = await store.get_occurrence(occurrence_id)
        assert occ is not None
        assert occ.agent_id == "agent-x"

    async def test_record_stores_context(self, store: ErrorStore) -> None:
        occurrence_id = await store.record_error(
            error_code=101, context="test context"
        )
        occ = await store.get_occurrence(occurrence_id)
        assert occ is not None
        assert occ.context == "test context"

    async def test_record_stores_stack_trace(self, store: ErrorStore) -> None:
        occurrence_id = await store.record_error(
            error_code=101, stack_trace="Traceback (most recent call last):\n..."
        )
        occ = await store.get_occurrence(occurrence_id)
        assert occ is not None
        assert "Traceback" in occ.stack_trace

    async def test_record_with_explicit_timestamp(self, store: ErrorStore) -> None:
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        occurrence_id = await store.record_error(error_code=101, timestamp=ts)
        occ = await store.get_occurrence(occurrence_id)
        assert occ is not None
        assert "2024-01-15" in occ.timestamp

    async def test_multiple_records_have_unique_ids(self, store: ErrorStore) -> None:
        id_a = await store.record_error(error_code=101)
        id_b = await store.record_error(error_code=101)
        assert id_a != id_b

    async def test_record_agent_error_convenience(
        self, store: ErrorStore, sample_error: AgentError
    ) -> None:
        occurrence_id = await store.record_agent_error(
            error=sample_error,
            agent_id="agent-y",
            context="wrapper test",
        )
        occ = await store.get_occurrence(occurrence_id)
        assert occ is not None
        assert occ.error_code == sample_error.code
        assert occ.agent_id == "agent-y"


# ---------------------------------------------------------------------------
# Query method tests
# ---------------------------------------------------------------------------


class TestGetErrorsByAgent:
    async def test_returns_only_matching_agent(self, store: ErrorStore) -> None:
        await store.record_error(error_code=101, agent_id="agent-a")
        await store.record_error(error_code=201, agent_id="agent-b")
        results = await store.get_errors_by_agent("agent-a")
        assert all(o.agent_id == "agent-a" for o in results)

    async def test_returns_all_errors_for_agent(self, store: ErrorStore) -> None:
        for code in [101, 102, 103]:
            await store.record_error(error_code=code, agent_id="agent-z")
        results = await store.get_errors_by_agent("agent-z")
        assert len(results) == 3

    async def test_unknown_agent_returns_empty_list(self, store: ErrorStore) -> None:
        results = await store.get_errors_by_agent("nonexistent-agent")
        assert results == []


class TestGetErrorsByCode:
    async def test_returns_matching_errors(self, store: ErrorStore) -> None:
        await store.record_error(error_code=103, agent_id="a1")
        await store.record_error(error_code=103, agent_id="a2")
        await store.record_error(error_code=201, agent_id="a3")
        results = await store.get_errors_by_code(103)
        assert len(results) == 2
        assert all(o.error_code == 103 for o in results)

    async def test_no_matches_returns_empty_list(self, store: ErrorStore) -> None:
        results = await store.get_errors_by_code(999)
        assert results == []


class TestGetErrorFrequency:
    async def test_returns_dict(self, store: ErrorStore) -> None:
        result = await store.get_error_frequency()
        assert isinstance(result, dict)

    async def test_correct_counts(self, store: ErrorStore) -> None:
        await store.record_error(error_code=101)
        await store.record_error(error_code=101)
        await store.record_error(error_code=201)
        freq = await store.get_error_frequency()
        assert freq[101] == 2
        assert freq[201] == 1

    async def test_empty_store_returns_empty_dict(self, store: ErrorStore) -> None:
        freq = await store.get_error_frequency()
        assert freq == {}

    async def test_only_recorded_codes_appear(self, store: ErrorStore) -> None:
        await store.record_error(error_code=301)
        freq = await store.get_error_frequency()
        assert 301 in freq
        assert 101 not in freq


class TestGetRecentErrors:
    async def test_returns_list(self, store: ErrorStore) -> None:
        result = await store.get_recent_errors()
        assert isinstance(result, list)

    async def test_limit_respected(self, store: ErrorStore) -> None:
        for code in [101, 102, 103, 201, 202]:
            await store.record_error(error_code=code)
        results = await store.get_recent_errors(limit=3)
        assert len(results) <= 3

    async def test_empty_store_returns_empty_list(self, store: ErrorStore) -> None:
        results = await store.get_recent_errors()
        assert results == []

    async def test_all_errors_returned_when_within_limit(
        self, store: ErrorStore
    ) -> None:
        for code in [101, 201]:
            await store.record_error(error_code=code)
        results = await store.get_recent_errors(limit=10)
        assert len(results) == 2


class TestGetErrorsByCategory:
    async def test_returns_matching_category_occurrences(
        self, store: ErrorStore
    ) -> None:
        # Code 101 is ErrorCategory.model
        await store.record_error(error_code=101, agent_id="a1")
        # Code 201 is ErrorCategory.tool
        await store.record_error(error_code=201, agent_id="a2")
        results = await store.get_errors_by_category(ErrorCategory.model)
        assert all(o.error_code in {101, 102, 103, 104, 105, 106} for o in results)
        assert len(results) == 1

    async def test_no_matching_category_returns_empty_list(
        self, store: ErrorStore
    ) -> None:
        await store.record_error(error_code=101)
        results = await store.get_errors_by_category(ErrorCategory.tool)
        assert results == []


class TestTotalCount:
    async def test_starts_at_zero(self, store: ErrorStore) -> None:
        count = await store.total_count()
        assert count == 0

    async def test_increments_with_records(self, store: ErrorStore) -> None:
        await store.record_error(error_code=101)
        await store.record_error(error_code=201)
        count = await store.total_count()
        assert count == 2


class TestDeleteOccurrence:
    async def test_delete_returns_true_for_existing(self, store: ErrorStore) -> None:
        occurrence_id = await store.record_error(error_code=101)
        result = await store.delete_occurrence(occurrence_id)
        assert result is True

    async def test_deleted_occurrence_not_found(self, store: ErrorStore) -> None:
        occurrence_id = await store.record_error(error_code=101)
        await store.delete_occurrence(occurrence_id)
        occ = await store.get_occurrence(occurrence_id)
        assert occ is None

    async def test_delete_nonexistent_returns_false(self, store: ErrorStore) -> None:
        result = await store.delete_occurrence("nonexistent-uuid")
        assert result is False

    async def test_delete_decrements_total_count(self, store: ErrorStore) -> None:
        occurrence_id = await store.record_error(error_code=101)
        await store.delete_occurrence(occurrence_id)
        count = await store.total_count()
        assert count == 0


class TestAllOccurrences:
    async def test_returns_all_stored_occurrences(self, store: ErrorStore) -> None:
        for code in [101, 201, 301]:
            await store.record_error(error_code=code)
        results = await store.all_occurrences(limit=10)
        assert len(results) == 3

    async def test_limit_is_respected(self, store: ErrorStore) -> None:
        for code in [101, 201, 301, 401, 501]:
            await store.record_error(error_code=code)
        results = await store.all_occurrences(limit=2)
        assert len(results) <= 2

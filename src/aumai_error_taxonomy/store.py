"""Persistence layer for classified error occurrences via aumai-store."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from aumai_store import Repository, Store
from pydantic import BaseModel, Field

from aumai_error_taxonomy.models import AgentError, ErrorCategory


class ErrorOccurrence(BaseModel):
    """A record of a single error occurrence produced by an agent.

    Attributes:
        id: UUID primary key, auto-generated if empty.
        error_code: Numeric error code from the taxonomy.
        timestamp: UTC datetime when the error was observed.
        agent_id: Identifier of the agent that produced the error.
        context: Free-form human-readable context string.
        stack_trace: Optional Python stack-trace text captured at the time.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    error_code: int
    timestamp: str = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    agent_id: str = ""
    context: str = ""
    stack_trace: str = ""


class ErrorStore:
    """Persist and query :class:`ErrorOccurrence` records via aumai-store.

    ``ErrorStore`` wraps a :class:`~aumai_store.core.Store` and exposes
    high-level query helpers on top of the raw
    :class:`~aumai_store.repository.Repository` API.

    Use :meth:`create` to construct and initialise the store before performing
    any operations.

    Example::

        store = await ErrorStore.create()
        occurrence_id = await store.record_error(
            error_code=103,
            agent_id="agent-1",
            context="model took too long to respond",
        )
        occurrences = await store.get_errors_by_agent("agent-1")
    """

    def __init__(self, store: Store) -> None:
        self._store = store
        self._repo: Repository[ErrorOccurrence] | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    async def create(cls, store: Store | None = None) -> ErrorStore:
        """Initialise an :class:`ErrorStore` backed by *store*.

        If *store* is ``None`` an in-memory store is created automatically
        (suitable for tests and ephemeral usage).

        Args:
            store: An already-initialised :class:`~aumai_store.core.Store`, or
                ``None`` to create a new in-memory store.

        Returns:
            A ready-to-use :class:`ErrorStore`.
        """
        effective_store = store or Store.memory()
        await effective_store.initialize()
        instance = cls(effective_store)
        instance._repo = await effective_store.prepare_repository(
            ErrorOccurrence, table_name="error_occurrences"
        )
        return instance

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    async def record_error(
        self,
        error_code: int,
        agent_id: str = "",
        context: str = "",
        stack_trace: str = "",
        timestamp: datetime | None = None,
    ) -> str:
        """Persist a new error occurrence and return its id.

        Args:
            error_code: Numeric error code from the taxonomy.
            agent_id: Identifier of the originating agent.
            context: Human-readable context string.
            stack_trace: Optional stack-trace text.
            timestamp: Override the observation timestamp.  Defaults to now.

        Returns:
            The UUID string assigned to the persisted :class:`ErrorOccurrence`.

        Raises:
            RuntimeError: If the store has not been initialised.
        """
        self._ensure_ready()
        effective_ts = (
            timestamp.isoformat()
            if timestamp is not None
            else datetime.now(tz=timezone.utc).isoformat()
        )
        occurrence = ErrorOccurrence(
            error_code=error_code,
            agent_id=agent_id,
            context=context,
            stack_trace=stack_trace,
            timestamp=effective_ts,
        )
        assert self._repo is not None  # noqa: S101  (mypy narrowing)
        return await self._repo.save(occurrence)

    async def record_agent_error(
        self,
        error: AgentError,
        agent_id: str = "",
        context: str = "",
        stack_trace: str = "",
    ) -> str:
        """Convenience wrapper — record a full :class:`AgentError` occurrence.

        Args:
            error: The :class:`~aumai_error_taxonomy.models.AgentError` that was
                classified.
            agent_id: Identifier of the originating agent.
            context: Human-readable context string.
            stack_trace: Optional stack-trace text.

        Returns:
            The UUID string assigned to the new :class:`ErrorOccurrence`.
        """
        return await self.record_error(
            error_code=error.code,
            agent_id=agent_id,
            context=context,
            stack_trace=stack_trace,
        )

    async def delete_occurrence(self, occurrence_id: str) -> bool:
        """Delete a single occurrence by its UUID.

        Args:
            occurrence_id: The UUID of the :class:`ErrorOccurrence` to delete.

        Returns:
            ``True`` if the record existed and was deleted.
        """
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        return await self._repo.delete(occurrence_id)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    async def get_occurrence(self, occurrence_id: str) -> ErrorOccurrence | None:
        """Fetch a single occurrence by UUID.

        Args:
            occurrence_id: The UUID of the :class:`ErrorOccurrence` to fetch.

        Returns:
            :class:`ErrorOccurrence` or ``None`` if not found.
        """
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        return await self._repo.get(occurrence_id)

    async def get_errors_by_agent(self, agent_id: str) -> list[ErrorOccurrence]:
        """Return all occurrences produced by *agent_id*.

        Args:
            agent_id: Agent identifier to filter on.

        Returns:
            List of :class:`ErrorOccurrence` records for *agent_id*.
        """
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        return await self._repo.find(agent_id=agent_id)

    async def get_errors_by_code(self, error_code: int) -> list[ErrorOccurrence]:
        """Return all occurrences for a specific numeric error code.

        Args:
            error_code: Numeric error code to filter on.

        Returns:
            List of matching :class:`ErrorOccurrence` records.
        """
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        return await self._repo.find(error_code=error_code)

    async def get_error_frequency(self) -> dict[int, int]:
        """Return a mapping of error code to occurrence count.

        Returns:
            Dictionary mapping each error code to the number of times it was
            recorded.
        """
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        all_occurrences = await self._repo.all(limit=100_000)
        frequency: dict[int, int] = {}
        for occurrence in all_occurrences:
            frequency[occurrence.error_code] = (
                frequency.get(occurrence.error_code, 0) + 1
            )
        return frequency

    async def get_recent_errors(self, limit: int = 20) -> list[ErrorOccurrence]:
        """Return the *limit* most recently recorded occurrences.

        Occurrences are ordered by :attr:`~ErrorOccurrence.timestamp` descending
        (newest first).

        Args:
            limit: Maximum number of occurrences to return.

        Returns:
            List of the most recent :class:`ErrorOccurrence` records.
        """
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        all_occurrences = await self._repo.all(limit=100_000)
        sorted_occurrences = sorted(
            all_occurrences,
            key=lambda o: o.timestamp,
            reverse=True,
        )
        return sorted_occurrences[:limit]

    async def get_errors_by_category(
        self,
        category: ErrorCategory,
        error_code_map: dict[int, AgentError] | None = None,
    ) -> list[ErrorOccurrence]:
        """Return all occurrences whose code belongs to *category*.

        Args:
            category: The :class:`~aumai_error_taxonomy.models.ErrorCategory` to
                filter by.
            error_code_map: Optional pre-built code → error mapping.  Defaults
                to the global ``ERROR_REGISTRY``.

        Returns:
            List of matching :class:`ErrorOccurrence` records.
        """
        from aumai_error_taxonomy.core import ERROR_REGISTRY

        effective_map: dict[int, AgentError] = (
            error_code_map if error_code_map is not None else ERROR_REGISTRY
        )
        category_codes = {
            code
            for code, error in effective_map.items()
            if error.category == category
        }
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        all_occurrences = await self._repo.all(limit=100_000)
        return [o for o in all_occurrences if o.error_code in category_codes]

    async def total_count(self) -> int:
        """Return the total number of stored occurrences.

        Returns:
            Total row count.
        """
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        return await self._repo.count()

    async def all_occurrences(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ErrorOccurrence]:
        """Return paginated occurrences with no ordering guarantee.

        Args:
            limit: Maximum number of rows.
            offset: Rows to skip.

        Returns:
            List of :class:`ErrorOccurrence` instances.
        """
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        return await self._repo.all(limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Repository access
    # ------------------------------------------------------------------

    @property
    def repository(self) -> Repository[ErrorOccurrence]:
        """Direct access to the underlying :class:`~aumai_store.repository.Repository`.

        Returns:
            The :class:`~aumai_store.repository.Repository` managing
            :class:`ErrorOccurrence` rows.

        Raises:
            RuntimeError: If the store has not been initialised via :meth:`create`.
        """
        self._ensure_ready()
        assert self._repo is not None  # noqa: S101
        return self._repo

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_ready(self) -> None:
        """Raise :class:`RuntimeError` when the store is not initialised."""
        if self._repo is None:
            raise RuntimeError(
                "ErrorStore has not been initialised. "
                "Use 'await ErrorStore.create()' to create a ready instance."
            )

    # ------------------------------------------------------------------
    # Lifecycle (thin wrappers so callers can close the underlying store)
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying :class:`~aumai_store.core.Store`."""
        await self._store.close()

    async def __aenter__(self) -> ErrorStore:
        """Support ``async with ErrorStore.create() as store: ...`` pattern."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close the underlying store on context manager exit."""
        await self.close()


__all__ = [
    "ErrorOccurrence",
    "ErrorStore",
]

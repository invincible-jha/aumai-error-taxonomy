"""Async API for aumai-error-taxonomy powered by aumai-async-core."""

from __future__ import annotations

from typing import Any

from aumai_async_core import AsyncEventEmitter, AsyncService, AsyncServiceConfig

from aumai_error_taxonomy.core import (
    ERROR_REGISTRY,
    UnknownErrorCode,
    classify_exception,
    create_error_response,
    errors_by_category,
    lookup_error,
)
from aumai_error_taxonomy.models import AgentError, ErrorCategory


class AsyncErrorRegistry(AsyncService):
    """Async-capable error registry built on top of :class:`AsyncService`.

    Wraps the synchronous core functions with async equivalents and emits
    events via an :class:`AsyncEventEmitter` whenever an error is classified
    or looked up.

    Event names emitted:

    - ``"error.classified"`` — after :meth:`classify_exception` resolves an
      error.  Keyword args: ``error_code``, ``error_name``, ``category``,
      ``retryable``, ``severity``.
    - ``"error.looked_up"`` — after :meth:`lookup_error` resolves a code.
      Keyword args: ``error_code``, ``error_name``.
    - ``"error.lookup_failed"`` — when :meth:`lookup_error` raises
      :class:`~aumai_error_taxonomy.core.UnknownErrorCode`.
      Keyword args: ``error_code``.

    Example::

        config = AsyncServiceConfig(name="error-registry")
        async with AsyncErrorRegistry(config) as registry:
            error = await registry.classify_exception(TimeoutError("timed out"))
            print(error.code)  # 103
    """

    def __init__(self, config: AsyncServiceConfig | None = None) -> None:
        effective_config = config or AsyncServiceConfig(
            name="aumai-error-taxonomy",
            health_check_interval_seconds=0.0,
        )
        super().__init__(effective_config)
        self._emitter: AsyncEventEmitter = AsyncEventEmitter()

    # ------------------------------------------------------------------
    # Event emitter access
    # ------------------------------------------------------------------

    @property
    def emitter(self) -> AsyncEventEmitter:
        """The :class:`AsyncEventEmitter` used for internal event emission."""
        return self._emitter

    # ------------------------------------------------------------------
    # Async lifecycle hooks
    # ------------------------------------------------------------------

    async def on_start(self) -> None:
        """No-op start hook — the registry is stateless and always ready."""

    async def on_stop(self) -> None:
        """No-op stop hook — clears all event listeners on shutdown."""
        self._emitter.remove_all_listeners()

    async def health_check(self) -> bool:
        """Return ``True`` when the error registry is populated."""
        return len(ERROR_REGISTRY) > 0

    # ------------------------------------------------------------------
    # Async core API
    # ------------------------------------------------------------------

    async def lookup_error(self, code: int) -> AgentError:
        """Async version of :func:`~aumai_error_taxonomy.core.lookup_error`.

        Looks up *code* in the global error registry and emits an event.

        Args:
            code: Numeric error code to resolve.

        Returns:
            The matching :class:`~aumai_error_taxonomy.models.AgentError`.

        Raises:
            :class:`~aumai_error_taxonomy.core.UnknownErrorCode`: When *code*
                is not registered.
        """
        await self.increment_request_count()
        try:
            error = lookup_error(code)
        except UnknownErrorCode:
            await self.increment_error_count()
            await self._emitter.emit(
                "error.lookup_failed",
                error_code=code,
            )
            raise
        await self._emitter.emit(
            "error.looked_up",
            error_code=error.code,
            error_name=error.name,
        )
        return error

    async def classify_exception(self, exc: BaseException) -> AgentError:
        """Async version of :func:`~aumai_error_taxonomy.core.classify_exception`.

        Maps *exc* to the closest :class:`~aumai_error_taxonomy.models.AgentError`
        and emits an ``"error.classified"`` event.

        Args:
            exc: Any Python exception instance.

        Returns:
            The best-matching :class:`~aumai_error_taxonomy.models.AgentError`.
        """
        await self.increment_request_count()
        error = classify_exception(exc)
        await self._emitter.emit(
            "error.classified",
            error_code=error.code,
            error_name=error.name,
            category=error.category.value,
            retryable=error.retryable,
            severity=error.severity,
        )
        return error

    async def errors_by_category(self, category: ErrorCategory) -> list[AgentError]:
        """Async version of :func:`~aumai_error_taxonomy.core.errors_by_category`.

        Args:
            category: The :class:`~aumai_error_taxonomy.models.ErrorCategory` to
                filter by.

        Returns:
            Sorted list of :class:`~aumai_error_taxonomy.models.AgentError`
            instances belonging to *category*.
        """
        await self.increment_request_count()
        return errors_by_category(category)

    async def create_error_response(
        self,
        error: AgentError,
        details: str | None = None,
    ) -> dict[str, Any]:
        """Async wrapper for :func:`~aumai_error_taxonomy.core.create_error_response`.

        Args:
            error: The :class:`~aumai_error_taxonomy.models.AgentError` to format.
            details: Optional human-readable extra context.

        Returns:
            JSON-serialisable error response dictionary.
        """
        await self.increment_request_count()
        return create_error_response(error, details=details)

    async def list_all_errors(self) -> list[AgentError]:
        """Return all registered errors sorted by numeric code.

        Returns:
            List of every :class:`~aumai_error_taxonomy.models.AgentError` in the
            global registry, ordered by :attr:`~AgentError.code`.
        """
        await self.increment_request_count()
        return sorted(ERROR_REGISTRY.values(), key=lambda e: e.code)

    async def registry_size(self) -> int:
        """Return the total number of registered error codes.

        Returns:
            Count of error codes in the global registry.
        """
        return len(ERROR_REGISTRY)


__all__ = [
    "AsyncErrorRegistry",
]

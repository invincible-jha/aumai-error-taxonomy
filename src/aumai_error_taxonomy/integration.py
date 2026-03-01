"""AumOS integration for aumai-error-taxonomy."""

from __future__ import annotations

import logging
from typing import Any

from aumai_integration import AumOS, Event, EventBus
from aumai_integration.models import ServiceInfo

from aumai_error_taxonomy.models import AgentError, ErrorCategory

logger = logging.getLogger(__name__)

_SERVICE_NAME = "aumai-error-taxonomy"
_SERVICE_VERSION = "0.1.0"
_SERVICE_DESCRIPTION = (
    "Standardised agent error codes, classification, and taxonomy for AumAI agents."
)
_SERVICE_CAPABILITIES = [
    "error_classification",
    "error_taxonomy",
    "error_lookup",
    "error_persistence",
    "recovery_suggestions",
]


# ---------------------------------------------------------------------------
# AumOS registration helpers
# ---------------------------------------------------------------------------


def register_with_aumos(hub: AumOS | None = None) -> AumOS:
    """Register the error-taxonomy service with an :class:`~aumai_integration.AumOS` hub.

    If *hub* is ``None`` the global AumOS singleton is used.

    Args:
        hub: An :class:`~aumai_integration.AumOS` instance.  Defaults to
            ``AumOS.instance()``.

    Returns:
        The hub the service was registered with.
    """
    effective_hub = hub if hub is not None else AumOS.instance()
    service_info = ServiceInfo(
        name=_SERVICE_NAME,
        version=_SERVICE_VERSION,
        description=_SERVICE_DESCRIPTION,
        capabilities=list(_SERVICE_CAPABILITIES),
        endpoints={},
        metadata={
            "error_count": 30,
            "categories": [c.value for c in ErrorCategory],
        },
    )
    effective_hub.register(service_info)
    logger.info(
        "aumai-error-taxonomy v%s registered with AumOS.", _SERVICE_VERSION
    )
    return effective_hub


def unregister_from_aumos(hub: AumOS | None = None) -> None:
    """Unregister the error-taxonomy service from *hub*.

    Args:
        hub: An :class:`~aumai_integration.AumOS` instance.  Defaults to
            ``AumOS.instance()``.
    """
    effective_hub = hub if hub is not None else AumOS.instance()
    effective_hub.unregister(_SERVICE_NAME)
    logger.info("aumai-error-taxonomy unregistered from AumOS.")


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------


async def publish_error_classified(
    event_bus: EventBus,
    error: AgentError,
    agent_id: str = "",
    context: str = "",
    extra_data: dict[str, Any] | None = None,
) -> int:
    """Publish an ``"error.classified"`` event to *event_bus*.

    Args:
        event_bus: The :class:`~aumai_integration.EventBus` to publish to.
        error: The classified :class:`~aumai_error_taxonomy.models.AgentError`.
        agent_id: Optional identifier of the originating agent.
        context: Optional human-readable context string.
        extra_data: Additional key-value pairs merged into the event data.

    Returns:
        The number of subscribers that received the event.
    """
    data: dict[str, Any] = {
        "error_code": error.code,
        "error_name": error.name,
        "category": error.category.value,
        "severity": error.severity,
        "retryable": error.retryable,
        "agent_id": agent_id,
        "context": context,
    }
    if extra_data:
        data.update(extra_data)
    return await event_bus.publish_simple(
        "error.classified",
        source=_SERVICE_NAME,
        **data,
    )


async def publish_error_looked_up(
    event_bus: EventBus,
    error: AgentError,
    agent_id: str = "",
) -> int:
    """Publish an ``"error.looked_up"`` event to *event_bus*.

    Args:
        event_bus: The :class:`~aumai_integration.EventBus` to publish to.
        error: The :class:`~aumai_error_taxonomy.models.AgentError` that was
            retrieved.
        agent_id: Optional identifier of the requesting agent.

    Returns:
        The number of subscribers that received the event.
    """
    return await event_bus.publish_simple(
        "error.looked_up",
        source=_SERVICE_NAME,
        error_code=error.code,
        error_name=error.name,
        category=error.category.value,
        agent_id=agent_id,
    )


async def publish_error_occurrence_recorded(
    event_bus: EventBus,
    error_code: int,
    occurrence_id: str,
    agent_id: str = "",
) -> int:
    """Publish an ``"error.occurrence_recorded"`` event to *event_bus*.

    Args:
        event_bus: The :class:`~aumai_integration.EventBus` to publish to.
        error_code: Numeric error code that was persisted.
        occurrence_id: UUID of the newly created
            :class:`~aumai_error_taxonomy.store.ErrorOccurrence`.
        agent_id: Optional identifier of the originating agent.

    Returns:
        The number of subscribers that received the event.
    """
    return await event_bus.publish_simple(
        "error.occurrence_recorded",
        source=_SERVICE_NAME,
        error_code=error_code,
        occurrence_id=occurrence_id,
        agent_id=agent_id,
    )


# ---------------------------------------------------------------------------
# Event subscription helpers
# ---------------------------------------------------------------------------


def subscribe_to_error_events(
    event_bus: EventBus,
    handler: Any,
    *,
    subscriber: str = "error-taxonomy-consumer",
) -> str:
    """Subscribe *handler* to all ``"error.*"`` events on *event_bus*.

    Args:
        event_bus: The :class:`~aumai_integration.EventBus` to subscribe to.
        handler: Async callable that accepts a single
            :class:`~aumai_integration.Event` argument.
        subscriber: Human-readable name for the subscriber.

    Returns:
        Opaque subscription ID that can be passed to
        :meth:`~aumai_integration.EventBus.unsubscribe`.
    """
    return event_bus.subscribe("error.*", handler, subscriber=subscriber)


def subscribe_to_classified_events(
    event_bus: EventBus,
    handler: Any,
    *,
    subscriber: str = "error-classified-consumer",
) -> str:
    """Subscribe *handler* to ``"error.classified"`` events only.

    Args:
        event_bus: The :class:`~aumai_integration.EventBus` to subscribe to.
        handler: Async callable that accepts a single
            :class:`~aumai_integration.Event` argument.
        subscriber: Human-readable name for the subscriber.

    Returns:
        Opaque subscription ID.
    """
    return event_bus.subscribe("error.classified", handler, subscriber=subscriber)


# ---------------------------------------------------------------------------
# Integrated classify-and-publish helper
# ---------------------------------------------------------------------------


async def classify_and_publish(
    exc: BaseException,
    event_bus: EventBus,
    agent_id: str = "",
    context: str = "",
) -> AgentError:
    """Classify *exc* and immediately publish an ``"error.classified"`` event.

    This is a convenience wrapper that combines
    :func:`~aumai_error_taxonomy.core.classify_exception` with
    :func:`publish_error_classified`.

    Args:
        exc: The exception to classify.
        event_bus: The :class:`~aumai_integration.EventBus` to publish to.
        agent_id: Optional identifier of the originating agent.
        context: Optional human-readable context string.

    Returns:
        The classified :class:`~aumai_error_taxonomy.models.AgentError`.
    """
    from aumai_error_taxonomy.core import classify_exception

    error = classify_exception(exc)
    await publish_error_classified(
        event_bus=event_bus,
        error=error,
        agent_id=agent_id,
        context=context,
    )
    return error


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "register_with_aumos",
    "unregister_from_aumos",
    "publish_error_classified",
    "publish_error_looked_up",
    "publish_error_occurrence_recorded",
    "subscribe_to_error_events",
    "subscribe_to_classified_events",
    "classify_and_publish",
]

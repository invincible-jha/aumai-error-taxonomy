"""Tests for aumai_error_taxonomy.integration — AumOS registration and event bus."""

from __future__ import annotations

import pytest

from aumai_integration import AumOS, Event, EventBus

from aumai_error_taxonomy.integration import (
    _SERVICE_CAPABILITIES,
    _SERVICE_NAME,
    _SERVICE_VERSION,
    classify_and_publish,
    publish_error_classified,
    publish_error_looked_up,
    publish_error_occurrence_recorded,
    register_with_aumos,
    subscribe_to_classified_events,
    subscribe_to_error_events,
    unregister_from_aumos,
)
from aumai_error_taxonomy.models import AgentError, ErrorCategory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_hub() -> AumOS:
    """Return a fresh AumOS hub (not the singleton) for each test."""
    return AumOS()


@pytest.fixture()
def event_bus() -> EventBus:
    """Return a fresh EventBus for each test."""
    return EventBus()


@pytest.fixture()
def sample_error() -> AgentError:
    return AgentError(
        code=103,
        category=ErrorCategory.model,
        name="model_timeout",
        description="Model timed out.",
        retryable=True,
        severity="high",
    )


# ---------------------------------------------------------------------------
# register_with_aumos tests
# ---------------------------------------------------------------------------


class TestRegisterWithAumOS:
    def test_register_returns_hub(self, fresh_hub: AumOS) -> None:
        result = register_with_aumos(hub=fresh_hub)
        assert result is fresh_hub

    def test_service_appears_in_hub_after_registration(
        self, fresh_hub: AumOS
    ) -> None:
        register_with_aumos(hub=fresh_hub)
        service = fresh_hub.get_service(_SERVICE_NAME)
        assert service is not None

    def test_service_name_is_correct(self, fresh_hub: AumOS) -> None:
        register_with_aumos(hub=fresh_hub)
        service = fresh_hub.get_service(_SERVICE_NAME)
        assert service is not None
        assert service.name == _SERVICE_NAME

    def test_service_version_is_correct(self, fresh_hub: AumOS) -> None:
        register_with_aumos(hub=fresh_hub)
        service = fresh_hub.get_service(_SERVICE_NAME)
        assert service is not None
        assert service.version == _SERVICE_VERSION

    def test_service_capabilities_present(self, fresh_hub: AumOS) -> None:
        register_with_aumos(hub=fresh_hub)
        service = fresh_hub.get_service(_SERVICE_NAME)
        assert service is not None
        for capability in _SERVICE_CAPABILITIES:
            assert capability in service.capabilities

    def test_service_description_non_empty(self, fresh_hub: AumOS) -> None:
        register_with_aumos(hub=fresh_hub)
        service = fresh_hub.get_service(_SERVICE_NAME)
        assert service is not None
        assert len(service.description) > 0

    def test_service_metadata_has_error_count(self, fresh_hub: AumOS) -> None:
        register_with_aumos(hub=fresh_hub)
        service = fresh_hub.get_service(_SERVICE_NAME)
        assert service is not None
        assert "error_count" in service.metadata
        assert service.metadata["error_count"] > 0

    def test_service_metadata_has_categories(self, fresh_hub: AumOS) -> None:
        register_with_aumos(hub=fresh_hub)
        service = fresh_hub.get_service(_SERVICE_NAME)
        assert service is not None
        assert "categories" in service.metadata
        assert isinstance(service.metadata["categories"], list)

    def test_register_uses_singleton_when_hub_is_none(self) -> None:
        AumOS.reset()
        result = register_with_aumos(hub=None)
        assert result is not None
        AumOS.reset()

    def test_find_service_by_capability(self, fresh_hub: AumOS) -> None:
        register_with_aumos(hub=fresh_hub)
        services = fresh_hub.find_by_capability("error_classification")
        assert any(s.name == _SERVICE_NAME for s in services)


# ---------------------------------------------------------------------------
# unregister_from_aumos tests
# ---------------------------------------------------------------------------


class TestUnregisterFromAumOS:
    def test_unregister_removes_service(self, fresh_hub: AumOS) -> None:
        register_with_aumos(hub=fresh_hub)
        unregister_from_aumos(hub=fresh_hub)
        service = fresh_hub.get_service(_SERVICE_NAME)
        assert service is None

    def test_list_services_empty_after_unregister(self, fresh_hub: AumOS) -> None:
        register_with_aumos(hub=fresh_hub)
        unregister_from_aumos(hub=fresh_hub)
        services = fresh_hub.list_services()
        names = [s.name for s in services]
        assert _SERVICE_NAME not in names


# ---------------------------------------------------------------------------
# publish_error_classified tests
# ---------------------------------------------------------------------------


class TestPublishErrorClassified:
    async def test_returns_handler_count(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        count = await publish_error_classified(event_bus, sample_error)
        assert isinstance(count, int)

    async def test_zero_handlers_when_no_subscribers(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        count = await publish_error_classified(event_bus, sample_error)
        assert count == 0

    async def test_handler_receives_event(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(event_bus, sample_error)
        assert len(received) == 1

    async def test_event_type_is_error_classified(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(event_bus, sample_error)
        assert received[0].event_type == "error.classified"

    async def test_event_source_is_service_name(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(event_bus, sample_error)
        assert received[0].source == _SERVICE_NAME

    async def test_event_data_has_error_code(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(event_bus, sample_error)
        assert received[0].data["error_code"] == sample_error.code

    async def test_event_data_has_error_name(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(event_bus, sample_error)
        assert received[0].data["error_name"] == sample_error.name

    async def test_event_data_has_category(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(event_bus, sample_error)
        assert received[0].data["category"] == sample_error.category.value

    async def test_event_data_has_severity(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(event_bus, sample_error)
        assert received[0].data["severity"] == sample_error.severity

    async def test_event_data_has_retryable(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(event_bus, sample_error)
        assert received[0].data["retryable"] == sample_error.retryable

    async def test_extra_data_merged_into_event(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(
            event_bus, sample_error, extra_data={"custom_key": "custom_value"}
        )
        assert received[0].data["custom_key"] == "custom_value"

    async def test_agent_id_included_in_event_data(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await publish_error_classified(
            event_bus, sample_error, agent_id="agent-7"
        )
        assert received[0].data["agent_id"] == "agent-7"


# ---------------------------------------------------------------------------
# publish_error_looked_up tests
# ---------------------------------------------------------------------------


class TestPublishErrorLookedUp:
    async def test_handler_receives_event(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.looked_up", handler)
        await publish_error_looked_up(event_bus, sample_error)
        assert len(received) == 1

    async def test_event_type_is_error_looked_up(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.looked_up", handler)
        await publish_error_looked_up(event_bus, sample_error)
        assert received[0].event_type == "error.looked_up"

    async def test_event_data_has_error_code(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.looked_up", handler)
        await publish_error_looked_up(event_bus, sample_error)
        assert received[0].data["error_code"] == sample_error.code


# ---------------------------------------------------------------------------
# publish_error_occurrence_recorded tests
# ---------------------------------------------------------------------------


class TestPublishOccurrenceRecorded:
    async def test_handler_receives_event(self, event_bus: EventBus) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.occurrence_recorded", handler)
        await publish_error_occurrence_recorded(
            event_bus, error_code=103, occurrence_id="uuid-abc"
        )
        assert len(received) == 1

    async def test_event_data_has_occurrence_id(self, event_bus: EventBus) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.occurrence_recorded", handler)
        await publish_error_occurrence_recorded(
            event_bus, error_code=103, occurrence_id="uuid-xyz"
        )
        assert received[0].data["occurrence_id"] == "uuid-xyz"

    async def test_event_data_has_error_code(self, event_bus: EventBus) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.occurrence_recorded", handler)
        await publish_error_occurrence_recorded(
            event_bus, error_code=201, occurrence_id="uuid-123"
        )
        assert received[0].data["error_code"] == 201


# ---------------------------------------------------------------------------
# subscribe_to_error_events / subscribe_to_classified_events tests
# ---------------------------------------------------------------------------


class TestSubscribeHelpers:
    async def test_subscribe_to_error_events_returns_subscription_id(
        self, event_bus: EventBus
    ) -> None:
        async def handler(event: Event) -> None:
            pass

        subscription_id = subscribe_to_error_events(event_bus, handler)
        assert isinstance(subscription_id, str)

    async def test_subscribe_to_error_events_receives_classified_event(
        self, event_bus: EventBus, sample_error: AgentError
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        subscribe_to_error_events(event_bus, handler)
        await publish_error_classified(event_bus, sample_error)
        assert len(received) == 1

    async def test_subscribe_to_classified_events_returns_subscription_id(
        self, event_bus: EventBus
    ) -> None:
        async def handler(event: Event) -> None:
            pass

        subscription_id = subscribe_to_classified_events(event_bus, handler)
        assert isinstance(subscription_id, str)

    async def test_subscribe_to_classified_does_not_receive_other_events(
        self, event_bus: EventBus
    ) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        subscribe_to_classified_events(event_bus, handler)
        await event_bus.publish_simple("error.looked_up", source="test", error_code=101)
        assert len(received) == 0


# ---------------------------------------------------------------------------
# classify_and_publish tests
# ---------------------------------------------------------------------------


class TestClassifyAndPublish:
    async def test_returns_agent_error(self, event_bus: EventBus) -> None:
        error = await classify_and_publish(
            TimeoutError("timeout"), event_bus=event_bus
        )
        assert isinstance(error, AgentError)

    async def test_classifies_timeout_to_103(self, event_bus: EventBus) -> None:
        error = await classify_and_publish(
            TimeoutError("timeout"), event_bus=event_bus
        )
        assert error.code == 103

    async def test_publishes_event_to_bus(self, event_bus: EventBus) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await classify_and_publish(TimeoutError("timeout"), event_bus=event_bus)
        assert len(received) == 1

    async def test_event_contains_correct_code(self, event_bus: EventBus) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await classify_and_publish(
            PermissionError("denied"),
            event_bus=event_bus,
            agent_id="agent-5",
        )
        assert received[0].data["error_code"] == 302

    async def test_agent_id_in_published_event(self, event_bus: EventBus) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await classify_and_publish(
            ValueError("bad"), event_bus=event_bus, agent_id="agent-99"
        )
        assert received[0].data["agent_id"] == "agent-99"

    async def test_context_in_published_event(self, event_bus: EventBus) -> None:
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        event_bus.subscribe("error.classified", handler)
        await classify_and_publish(
            MemoryError("oom"),
            event_bus=event_bus,
            context="batch processing crashed",
        )
        assert received[0].data["context"] == "batch processing crashed"

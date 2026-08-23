"""Decoupled in-memory EventBus for domain event publish-subscribe architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
import time
from typing import Any, Callable, TypeVar
import uuid

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DomainEvent:
    """Base class for all domain events."""

    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


T = TypeVar("T", bound=DomainEvent)
EventHandler = Callable[[Any], None]


class EventBus:
    """Thread-safe in-memory publish-subscriber event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[type[DomainEvent], list[EventHandler]] = {}
        self._lock = RLock()

    def subscribe(self, event_type: type[T], handler: Callable[[T], None]) -> None:
        """Register an event handler for a specific domain event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug("Subscribed %s to event %s", handler.__name__, event_type.__name__)

    def unsubscribe(self, event_type: type[T], handler: Callable[[T], None]) -> None:
        """Unregister an event handler for a domain event type."""
        with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.debug("Unsubscribed %s from event %s", handler.__name__, event_type.__name__)

    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all registered subscribers."""
        event_type = type(event)
        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Error executing event handler %s for %s", getattr(handler, "__name__", str(handler)), event_type.__name__)

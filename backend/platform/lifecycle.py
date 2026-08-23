"""Lifecycle Manager and Recovery Manager services."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from backend.core.events.bus import EventBus
from backend.platform.runtime_events import RuntimeRecoveryTriggeredEvent, ShutdownInitiatedEvent
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class LifecycleManager:
    """Manages application startup and graceful shutdown sequences."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._startup_hooks: list[tuple[str, Callable[[], None]]] = []
        self._shutdown_hooks: list[tuple[str, Callable[[], None]]] = []
        self._is_shutdown = False
        self._lock = RLock()

    def register_startup_hook(self, name: str, fn: Callable[[], None]) -> None:
        """Register a startup hook function."""
        with self._lock:
            self._startup_hooks.append((name, fn))

    def register_shutdown_hook(self, name: str, fn: Callable[[], None]) -> None:
        """Register a shutdown hook function."""
        with self._lock:
            self._shutdown_hooks.append((name, fn))

    def startup(self) -> None:
        """Execute registered startup hooks sequentially."""
        with self._lock:
            logger.info("Executing LifecycleManager startup sequence...")
            for name, hook in self._startup_hooks:
                try:
                    logger.debug("Executing startup hook '%s'", name)
                    hook()
                except Exception as exc:
                    logger.exception("Startup hook '%s' failed: %s", name, exc)

    def shutdown(self, reason: str = "normal") -> None:
        """Execute registered shutdown hooks sequentially in reverse order."""
        with self._lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
            logger.info("Executing LifecycleManager graceful shutdown sequence (reason='%s')...", reason)

            if self._event_bus:
                self._event_bus.publish(ShutdownInitiatedEvent(reason=reason))

            for name, hook in reversed(self._shutdown_hooks):
                try:
                    logger.debug("Executing shutdown hook '%s'", name)
                    hook()
                except Exception as exc:
                    logger.exception("Shutdown hook '%s' failed: %s", name, exc)


class RecoveryManager:
    """Coordinates component failure recovery and degradation strategies."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._recovery_strategies: dict[str, Callable[[], bool]] = {}
        self._lock = RLock()

    def register_recovery_strategy(self, component_name: str, strategy_fn: Callable[[], bool]) -> None:
        """Register a recovery callback for a named component."""
        with self._lock:
            self._recovery_strategies[component_name] = strategy_fn

    def attempt_recovery(self, component_name: str) -> bool:
        """Execute registered recovery strategy for a component."""
        with self._lock:
            strategy = self._recovery_strategies.get(component_name)
            if not strategy:
                logger.warning("No recovery strategy registered for component '%s'", component_name)
                return False

            logger.info("Attempting runtime recovery for component '%s'", component_name)
            try:
                success = strategy()
                action_text = f"Recovery {'succeeded' if success else 'failed'}"
                if self._event_bus:
                    self._event_bus.publish(
                        RuntimeRecoveryTriggeredEvent(
                            component_name=component_name,
                            action_taken=action_text,
                        )
                    )
                return success
            except Exception as exc:
                logger.exception("Recovery strategy for '%s' raised exception: %s", component_name, exc)
                return False

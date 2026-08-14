"""Automated 3-Tier Recovery Policy Manager."""

from __future__ import annotations

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RecoveryPolicy:
    """Manages 3-tier recovery (Tier 1: Retry, Tier 2: Re-plan, Tier 3: Human Approval)."""

    def __init__(self, max_retries: int = 3) -> None:
        self._max_retries = max_retries

    def handle_failure(self, retry_count: int) -> str:
        """Determine recovery action based on retry count."""
        if retry_count < self._max_retries:
            logger.info("RecoveryPolicy Tier 1: Retry attempt %d/%d", retry_count + 1, self._max_retries)
            return "RETRY"
        if retry_count == self._max_retries:
            logger.info("RecoveryPolicy Tier 2: Re-planning workflow")
            return "REPLAN"

        logger.warning("RecoveryPolicy Tier 3: Escalating to human approval")
        return "AWAITING_HUMAN_APPROVAL"

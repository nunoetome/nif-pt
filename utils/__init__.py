"""utils — reservado para helpers v0.4.

Futuro: helpers de formatação, sanitização HTML.
Logging: TAG [util] + TIMING
"""

import logging
import time

logger = logging.getLogger(__name__)


def helper_placeholder():
    logger.debug(f"{' helper_placeholder() ':~^49}")
    t = time.perf_counter()
    logger.debug("[util] helper_placeholder() -> %.2fs", time.perf_counter() - t)

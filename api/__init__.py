"""api — reservado para FastAPI v0.4.

Futuro: GET /nif/{nif} -> consulta_nif.consultar_nif
Logging: TAG [api] + TIMING
"""

import logging
import time

logger = logging.getLogger(__name__)


def placeholder_api():
    logger.debug(f"{' placeholder_api() ':~^49}")
    t = time.perf_counter()
    logger.info("[api] Placeholder API — ainda não implementado")
    logger.debug("[api] placeholder_api() -> %.2fs", time.perf_counter() - t)

#!/usr/bin/env python3
"""
nif-pt — Ponto de entrada principal (stub orquestrador).

Futuro: argparse --nif --to {sqlite,azure,both} --file
Atual: demonstra BANNER_APP + BOX + logging.
"""

import logging
import sys
import time
from Logging.logging_orchestrator import setup_logging

logger = logging.getLogger(__name__)


def main():
    logger_main = setup_logging()
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt a iniciar ':=^49}")
    logger_main.info("=" * 49)
    t_app = time.perf_counter()

    logger_main.info("-" * 49)
    logger_main.info(f"{' Modo ':-^49}")
    logger_main.info("-" * 49)
    logger_main.info("[cli] NIF.pt - Recolha de dados")
    logger_main.info("[cli] Modo: scraping / API (por definir)")
    logger_main.info("[cli] Uso direto: python consulta_nif.py <NIF> | python importar_nif_sqlite.py")
    logger_main.info("[cli] Ver MANUAL.md para instruções completas")

    # BOX ajuda
    logger_main.info("-" * 49)
    logger_main.info("| nif-pt - Ajuda                                    |")
    logger_main.info("|-------------------------------------------------|")
    logger_main.info("| python consulta_nif.py 509442013               |")
    logger_main.info("| python consulta_nif.py 509442013 | python importar_nif_sqlite.py |")
    logger_main.info("| python consulta_nif.py 509442013 | python importar_nif.py |")
    logger_main.info("-" * 49)

    logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt finalizado ':=^49}")
    logger_main.info("=" * 49)

    # Mantém prints para compatibilidade stdout
    print("NIF.pt - Recolha de dados")
    print("Modo: scraping / API (por definir)")


if __name__ == "__main__":
    main()

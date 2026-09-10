#!/usr/bin/env python3
"""
main — Ponto de entrada orquestrador (stub) do nif-pt.

Futuro: ``argparse --nif --to {sqlite,azure,both} --file`` para orquestrar
:mod:`consulta_nif` + :mod:`importar_nif_sqlite` / :mod:`importar_nif` sem
``tee``. Atual: demonstra ``BANNER_APP`` + ``BOX`` + logging com
:mod:`Logging.logging_orchestrator`.

Uso:
    python main.py
    # Futuro:
    # python main.py --nif 509442013 --to both
    # python main.py --file nifs.txt --to sqlite

Exemplos:
    >>> import main  # doctest: +SKIP
    >>> main.main()  # doctest: +SKIP
    NIF.pt - Recolha de dados

See Also:
    :mod:`consulta_nif`, :mod:`importar_nif`, :mod:`importar_nif_sqlite`,
    :mod:`Logging.logging_orchestrator`
"""

import logging
import sys
import time
from Logging.logging_orchestrator import setup_logging
from utils.run_id import ensure_run_id, extract_cli_run_id, set_run_id

logger = logging.getLogger(__name__)


def main():
    """Executa o stub orquestrador — loga BANNERs + BOX de ajuda.

    Demonstra o livro de estilo R1–R9 (``= 49`` para app, ``- 49`` para
    secção, ``BOX`` ``| ... |``, TAG ``[cli]``, TIMING ``%.2fs``) e imprime
    ajuda de pipeline em ``stdout`` para compatibilidade.

    A função não recebe argumentos nem devolve valor; termina sempre com
    ``exit 0`` implícito. Futuramente aceitará ``argparse``.

    Returns:
        ``None`` — efeito colateral é logging + ``print`` em stdout.

    Examples:
        >>> main()  # doctest: +SKIP
        <<nif-pt>> INFO - ===================================================
        <<nif-pt>> INFO - ================ nif-pt a iniciar ===============
    """
    logger_main = setup_logging()
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt a iniciar ':=^49}")
    logger_main.info("=" * 49)
    t_app = time.perf_counter()

    # run_id único por execução — partilhado por futuros sub-módulos
    _run_id = ensure_run_id(cli_value=extract_cli_run_id())
    logger_main.info("[run] run_id=%s", _run_id)

    logger_main.info("-" * 49)
    logger_main.info(f"{' Modo ':-^49}")
    logger_main.info("-" * 49)
    logger_main.info("[cli] NIF.pt - Recolha de dados run_id=%s", _run_id[:8])
    logger_main.info("[cli] Modo: scraping / API (por definir)")
    logger_main.info("[cli] Uso direto: python consulta_nif.py <NIF> | python importar_nif_sqlite.py")
    logger_main.info("[cli] Ver MANUAL.md para instruções completas")
    logger_main.info("[run] run_id=%s", _run_id)

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

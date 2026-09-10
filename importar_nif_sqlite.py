#!/usr/bin/env python3
"""
importar_nif_sqlite — Persiste JSON do consulta_nif.py em SQLite local.

Cria ``data/nif_pt.db`` (WAL) e a tabela ``nif_pt`` se não existir, e insere
o JSON completo como ``TEXT`` (schemaless). Lê de ``stdin`` para operar em
pipeline Unix.

Uso:
    python consulta_nif.py 509442013 | python importar_nif_sqlite.py
    python importar_nif_sqlite.py < ficheiro.json
    python consulta_nif.py 509442013 > tmp.json && python importar_nif_sqlite.py < tmp.json

Configuração:
    Lida via :func:`config.config.get_config` (``importar_nif_sqlite``):

    * ``db_path`` — ``data/nif_pt.db`` (relativo à raiz)
    * ``tabela`` — ``nif_pt``

Esquema SQLite (``nif_pt`` — 4 colunas):
    * ``id INTEGER PRIMARY KEY AUTOINCREMENT``
    * ``nif INTEGER NOT NULL``
    * ``dados TEXT NOT NULL`` — ``json.dumps(resultado, ensure_ascii=False)``
    * ``data_consulta TEXT NOT NULL DEFAULT (datetime('now'))``

    ``PRAGMA journal_mode=WAL`` mitiga ``database is locked``.

Exemplos:
    >>> # pipeline (doctest: +SKIP)
    >>> # $ echo '{"nif":"509442013","erro":null,"dados":{"title":"X"}}' | python importar_nif_sqlite.py

See Also:
    :mod:`consulta_nif`, :mod:`importar_nif`, :mod:`utils.error_handler`
"""

import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from config.config import get_config
from Logging.logging_orchestrator import setup_logging

logger = logging.getLogger(__name__)

cfg = get_config("importar_nif_sqlite")

DB_PATH = Path(__file__).parent / cfg.get("db_path", "data/nif_pt.db")
TABELA = cfg.get("tabela", "nif_pt")

SQL_DDL = f"""
CREATE TABLE IF NOT EXISTS {TABELA} (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nif             INTEGER NOT NULL,
    dados           TEXT NOT NULL,
    data_consulta   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_db() -> sqlite3.Connection:
    """Abre (e cria se necessário) a ligação SQLite com WAL e DDL garantido.

    * Cria ``DB_PATH.parent`` com ``mkdir(parents=True, exist_ok=True)``.
    * Liga com ``sqlite3.connect(str(DB_PATH))``.
    * Executa ``PRAGMA journal_mode=WAL`` (logado, falha não fatal).
    * Executa ``SQL_DDL`` (``CREATE TABLE IF NOT EXISTS nif_pt``) e ``commit``.

    Returns:
        ``sqlite3.Connection`` aberta com WAL activo e tabela garantida.
        O chamador deve fazer ``cursor.close()`` / ``conn.close()``.

    Examples:
        >>> conn = get_db()  # doctest: +SKIP
        >>> conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()  # doctest: +SKIP
        [('nif_pt',)]

    Notas:
        * WAL permite leitura concorrente; para escrita concorrente intensa
          considerar ``PRAGMA busy_timeout=5000``.
        * TAG ``[sqlite]`` + TIMING (R9).
    """
    logger.debug(f"{' get_db() ':~^49}")
    t = time.perf_counter()
    logger.debug("[sqlite] DB_PATH=%s parent mkdir", DB_PATH)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    # WAL
    try:
        cur = conn.execute("PRAGMA journal_mode=WAL")
        wal_mode = cur.fetchone()
        logger.info("[sqlite] PRAGMA journal_mode=WAL -> %s", wal_mode[0] if wal_mode else "wal")
    except sqlite3.Error as e:
        logger.warning("[sqlite] Falha PRAGMA WAL: %s", e)
    conn.executescript(SQL_DDL)
    logger.debug("[sqlite] DDL nif_pt executado (tabela=%s)", TABELA)
    conn.commit()
    logger.debug("[sqlite] get_db() -> %.2fs", time.perf_counter() - t)
    return conn


def main():
    """Ponto de entrada CLI — lê JSON de stdin e insere em SQLite.

    Fluxo:

    1. ``setup_logging()`` + BANNER ``= 49``.
    2. ``sys.stdin.read()`` — ``exit 1`` se vazio (pipeline quebrado).
    3. ``json.loads`` — ``exit 1`` se inválido.
    4. Se ``resultado["erro"]`` existe → ``exit 1`` sem inserir (propaga erro
       do :mod:`consulta_nif`).
    5. ``get_db()`` + ``INSERT INTO nif_pt (nif, dados, data_consulta)
       VALUES (?, ?, ?)`` com ``json.dumps(resultado, ensure_ascii=False)``.
    6. BOX ``Guardado em SQLite`` + TIMING + BANNER fim.

    Args:
        Nenhum — lê ``sys.stdin`` integralmente.

    Returns:
        Não retorna — ``sys.exit(0)`` em sucesso, ``sys.exit(1)`` em erro.
        Mensagens humanas em ``stderr`` (não quebram pipe).

    Examples:
        >>> # $ python consulta_nif.py 509442013 | python importar_nif_sqlite.py  (doctest: +SKIP)
        >>> # <<nif-pt>> INFO - [sqlite] INSERT nif_pt nif=509442013 -> 1 row em 0.02s

    See Also:
        :func:`get_db`, :mod:`consulta_nif`, :mod:`utils.error_handler`
    """
    logger_main = setup_logging()
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt importar_nif_sqlite a iniciar ':=^49}")
    logger_main.info("=" * 49)
    t_app = time.perf_counter()

    raw = sys.stdin.read()
    logger_main.debug("[io] stdin lido %d bytes", len(raw))
    if not raw.strip():
        logger_main.error("[io] Nenhum JSON recebido no stdin (pipeline quebrado)")
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif_sqlite finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    try:
        resultado = json.loads(raw)
        logger_main.debug("[io] JSON carregado nif=%s", resultado.get("nif"))
    except json.JSONDecodeError as e:
        logger_main.error("[io] JSON inválido: %s (preview=%.80s)", e, raw[:80])
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif_sqlite finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    if resultado.get("erro"):
        logger_main.warning("[api] Erro consulta propagado: %s", resultado["erro"])
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif_sqlite finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    nif = resultado.get("nif")
    if not nif:
        logger_main.error("[io] NIF não encontrado no JSON")
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif_sqlite finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    logger_main.debug("-" * 49)

    conn = get_db()
    cursor = conn.cursor()

    try:
        dados_json = json.dumps(resultado, ensure_ascii=False)
        logger_main.debug("[sqlite] dados_json %d chars nif=%s", len(dados_json), nif)
        t_insert = time.perf_counter()
        cursor.execute(
            f"INSERT INTO {TABELA} (nif, dados, data_consulta) VALUES (?, ?, ?)",
            (nif, dados_json, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        logger_main.info("[sqlite] INSERT %s nif=%s -> 1 row em %.2fs", TABELA, nif, time.perf_counter() - t_insert)
        # BOX sucesso
        logger_main.info("-" * 49)
        logger_main.info("| Guardado em SQLite                                |")
        logger_main.info("|-------------------------------------------------|")
        logger_main.info("| NIF         : %-30s |", str(nif))
        logger_main.info("| Tabela      : %-30s |", TABELA)
        logger_main.info("| DB          : %-30s |", str(DB_PATH))
        logger_main.info("| Tempo       : %-30s |", f"{time.perf_counter() - t_app:.2f}s")
        logger_main.info("-" * 49)
    except sqlite3.Error as e:
        conn.rollback()
        logger_main.error("[sqlite] Falha inserção nif=%s: %s", nif, e)
        logger_main.warning("[sqlite] rollback executado")
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif_sqlite finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
        logger_main.debug("[sqlite] Ligação fechada")

    logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt importar_nif_sqlite finalizado ':=^49}")
    logger_main.info("=" * 49)


if __name__ == "__main__":
    main()

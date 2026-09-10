#!/usr/bin/env python3
"""
Guarda o JSON do consulta_nif.py numa base de dados SQLite.

Cria automaticamente a base de dados e a tabela se não existir.

Uso:
    python consulta_nif.py 509442013 | python importar_nif_sqlite.py
    python importar_nif_sqlite.py < ficheiro.json

A configuração é lida do config.yaml via config.py.
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

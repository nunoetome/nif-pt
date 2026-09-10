#!/usr/bin/env python3
"""
Importa o JSON do consulta_nif.py para a tabela de staging na Azure SQL.

Uso:
    python consulta_nif.py 509442013 | python importar_nif.py
    python importar_nif.py < ficheiro.json

Insere sempre em nif_pt_stg. O tratamento e migração para nif_pt
é feito posteriormente noutro processo.

A configuração (servidor, base de dados, schema, nomes das tabelas)
é lida do config.yaml e .env via config.py.
"""

import json
import logging
import sys
import time
from datetime import date, datetime

from config.config import get_config
from Logging.logging_orchestrator import setup_logging
import pyodbc

logger = logging.getLogger(__name__)

cfg = get_config("importar_nif")

SQL_SERVER = cfg.get("sql_server", "kiwa-pt-operations.database.windows.net")
SQL_DATABASE = cfg.get("sql_database", "kiwa-pt-operations")
SQL_SCHEMA = cfg.get("sql_schema", "stg_nunotome")
SQL_DRIVER = cfg.get("sql_driver", "ODBC Driver 18 for SQL Server")
TABELA_STAGING = f"{SQL_SCHEMA}.{cfg.get('tabela_staging', 'nif_pt_stg')}"
AZURE_USER = cfg.get("AZURE_USER", "")
AZURE_PALAVRA_CHAVE = cfg.get("AZURE_PALAVRA_CHAVE", "")


def connection_string() -> str:
    logger.debug(f"{' connection_string() ':~^49}")
    t = time.perf_counter()
    cs = (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={AZURE_USER};"
        f"PWD={AZURE_PALAVRA_CHAVE};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    logger.debug("[db] connection_string() -> %.2fs (driver=%s server=%s)", time.perf_counter() - t, SQL_DRIVER, SQL_SERVER)
    return cs


def extrair_cae(registo: dict) -> str | None:
    cae = registo.get("cae")
    if isinstance(cae, list):
        joined = ",".join(str(c) for c in cae)
        logger.debug("[map] extrair_cae lista %d -> '%s'", len(cae), joined[:80])
        return joined
    if cae is not None:
        logger.debug("[map] extrair_cae str -> '%s'", str(cae)[:80])
        return str(cae)
    return None


def parse_date(val) -> date | None:
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        result = datetime.fromisoformat(str(val).replace("Z", "")).date()
        logger.debug("[map] parse_date '%s' -> %s", val, result)
        return result
    except (ValueError, TypeError) as e:
        logger.debug("[map] parse_date falha '%s': %s", val, e)
        return None


def parse_capital(val) -> float | None:
    if not val:
        return None
    try:
        result = float(str(val).replace(",", "."))
        logger.debug("[map] parse_capital '%s' -> %s", val, result)
        return result
    except (ValueError, TypeError) as e:
        logger.debug("[map] parse_capital falha '%s': %s", val, e)
        return None


def parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        result = int(val)
        return result
    except (ValueError, TypeError) as e:
        logger.debug("[map] parse_int falha '%s': %s", val, e)
        return None


def mapear_registo(resultado: dict) -> dict:
    logger.debug(f"{' mapear_registo() ':~^49}")
    t = time.perf_counter()
    r = resultado.get("dados") or {}
    contactos = r.get("contacts") or {}
    estrutura = r.get("structure") or {}
    geo = r.get("geo") or {}
    place = r.get("place") or {}
    creditos = resultado.get("creditos") or {}
    creditos_left = creditos.get("left") or {}
    if isinstance(creditos_left, list):
        # free plan devolve [] em vez de dict
        logger.debug("[map] creditos.left é lista vazia (free plan) -> dict vazio")
        creditos_left = {}

    mapped = {
        "nif": parse_int(resultado.get("nif")),
        "nif_valido_formato": 1 if resultado.get("nif_valido_formato") else 0,
        "consulta_origem": resultado.get("fonte", "nif.pt"),
        "seo_url": r.get("seo_url"),
        "title": r.get("title"),
        "alias": r.get("alias"),
        "status": r.get("status"),
        "start_date": parse_date(r.get("start_date")),
        "activity": r.get("activity"),
        "place_address": place.get("address"),
        "place_pc4": place.get("pc4"),
        "place_pc3": place.get("pc3"),
        "place_city": place.get("city"),
        "address": r.get("address"),
        "pc4": r.get("pc4"),
        "pc3": r.get("pc3"),
        "city": r.get("city"),
        "geo_region": geo.get("region"),
        "geo_county": geo.get("county"),
        "geo_parish": geo.get("parish"),
        "contacts_email": contactos.get("email"),
        "contacts_phone": contactos.get("phone"),
        "contacts_website": contactos.get("website"),
        "contacts_fax": contactos.get("fax"),
        "structure_nature": estrutura.get("nature"),
        "structure_capital": parse_capital(estrutura.get("capital")),
        "structure_capital_currency": estrutura.get("capital_currency"),
        "cae": extrair_cae(r),
        "racius": r.get("racius"),
        "portugalio": r.get("portugalio"),
        "creditos_used": creditos.get("used"),
        "creditos_left_month": parse_int(creditos_left.get("month")),
        "creditos_left_day": parse_int(creditos_left.get("day")),
        "creditos_left_hour": parse_int(creditos_left.get("hour")),
        "creditos_left_minute": parse_int(creditos_left.get("minute")),
        "creditos_left_paid": parse_int(creditos_left.get("paid")),
    }

    logger.info(
        "[map] 36 cols mapeadas nif=%s title=%.30s cae=%s credits used=%s left_month=%s",
        mapped.get("nif"),
        (mapped.get("title") or "")[:30],
        (mapped.get("cae") or "")[:50],
        mapped.get("creditos_used"),
        mapped.get("creditos_left_month"),
    )
    logger.debug("[map] mapear_registo() -> %.2fs", time.perf_counter() - t)
    return mapped


def colunas_tabela() -> list[str]:
    return [
        "nif", "nif_valido_formato", "consulta_origem",
        "seo_url", "title", "alias", "status", "start_date", "activity",
        "place_address", "place_pc4", "place_pc3", "place_city",
        "address", "pc4", "pc3", "city",
        "geo_region", "geo_county", "geo_parish",
        "contacts_email", "contacts_phone", "contacts_website", "contacts_fax",
        "structure_nature", "structure_capital", "structure_capital_currency",
        "cae", "racius", "portugalio",
        "creditos_used", "creditos_left_month", "creditos_left_day",
        "creditos_left_hour", "creditos_left_minute", "creditos_left_paid",
    ]


def placeholders() -> str:
    return ",".join("?" for _ in colunas_tabela())


def valores_para_insert(reg: dict) -> list:
    cols = colunas_tabela()
    return [reg.get(c) for c in cols]


def main():
    logger_main = setup_logging()
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt importar_nif a iniciar ':=^49}")
    logger_main.info("=" * 49)
    t_app = time.perf_counter()

    raw = sys.stdin.read()
    logger_main.debug("[io] stdin lido %d bytes", len(raw))
    if not raw.strip():
        logger_main.error("[io] Nenhum JSON recebido no stdin (pipeline quebrado)")
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    try:
        resultado = json.loads(raw)
        logger_main.debug("[io] JSON carregado nif=%s", resultado.get("nif"))
    except json.JSONDecodeError as e:
        logger_main.error("[io] JSON inválido: %s (preview=%.80s)", e, raw[:80])
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    if resultado.get("erro"):
        logger_main.warning("[api] Erro consulta propagado: %s", resultado["erro"])
        # mostrar também message detalhada se existir em dados
        dados = resultado.get("dados") or {}
        if isinstance(dados, dict) and dados.get("message"):
            logger_main.warning("[api] Detalhe: %s", dados.get("message"))
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    nif = resultado.get("nif")
    if not nif:
        logger_main.error("[io] NIF não encontrado no JSON")
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    logger_main.debug("-" * 49)
    reg = mapear_registo(resultado)

    if not AZURE_USER or not AZURE_PALAVRA_CHAVE:
        logger_main.error("[cfg] AZURE_USER ou AZURE_PALAVRA_CHAVE não definidos no config/.env")
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    logger_main.info("-" * 49)
    logger_main.info(f"{' Inserir staging ':-^49}")
    logger_main.info("-" * 49)

    try:
        t_conn = time.perf_counter()
        masked_user = AZURE_USER[:3] + "***" if AZURE_USER and len(AZURE_USER) > 3 else "***"
        logger_main.info("[db] A ligar a %s/%s schema=%s user=%s driver=%s", SQL_SERVER, SQL_DATABASE, SQL_SCHEMA, masked_user, SQL_DRIVER)
        conn = pyodbc.connect(connection_string(), timeout=30)
        conn.autocommit = False
        cursor = conn.cursor()
        logger_main.debug("[db] Ligação estabelecida em %.2fs", time.perf_counter() - t_conn)
    except pyodbc.Error as e:
        logger_main.error("[db] Falha na ligação Azure SQL: %s", e)
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    cols = colunas_tabela()
    vals = valores_para_insert(reg)
    sql_insert_stg = (
        f"INSERT INTO {TABELA_STAGING} ({','.join(cols)}) "
        f"VALUES ({placeholders()})"
    )
    logger_main.debug("[db] SQL: %s", sql_insert_stg[:120])

    try:
        t_insert = time.perf_counter()
        cursor.execute(sql_insert_stg, vals)
        logger_main.info("[db] INSERT %s nif=%s -> 1 row em %.2fs", TABELA_STAGING, nif, time.perf_counter() - t_insert)
        conn.commit()
        logger_main.debug("[db] commit OK")
        # BOX sucesso
        logger_main.info("-" * 49)
        logger_main.info("| Inserido em Azure SQL                              |")
        logger_main.info("|-------------------------------------------------|")
        logger_main.info("| NIF         : %-30s |", str(nif))
        logger_main.info("| Tabela      : %-30s |", TABELA_STAGING[:30])
        logger_main.info("| Titulo      : %-30s |", (reg.get("title") or "")[:30])
        logger_main.info("| CAE         : %-30s |", (reg.get("cae") or "")[:30])
        logger_main.info("| Tempo       : %-30s |", f"{time.perf_counter() - t_app:.2f}s")
        logger_main.info("-" * 49)
    except pyodbc.Error as e:
        conn.rollback()
        logger_main.error("[db] Falha inserção nif=%s: %s", nif, e)
        logger_main.warning("[db] rollback executado")
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)
    finally:
        try:
            cursor.close()
            conn.close()
            logger_main.debug("[db] Ligação fechada")
        except Exception:
            pass

    logger_main.info("Importar concluído em %.2fs", time.perf_counter() - t_app)
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
    logger_main.info("=" * 49)


if __name__ == "__main__":
    main()

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

import sys
import json
from datetime import date, datetime
from config.config import get_config
import pyodbc


cfg = get_config("importar_nif")

SQL_SERVER = cfg.get("sql_server", "kiwa-pt-operations.database.windows.net")
SQL_DATABASE = cfg.get("sql_database", "kiwa-pt-operations")
SQL_SCHEMA = cfg.get("sql_schema", "stg_nunotome")
SQL_DRIVER = cfg.get("sql_driver", "ODBC Driver 18 for SQL Server")
TABELA_STAGING = f"{SQL_SCHEMA}.{cfg.get('tabela_staging', 'nif_pt_stg')}"
AZURE_USER = cfg.get("AZURE_USER", "")
AZURE_PALAVRA_CHAVE = cfg.get("AZURE_PALAVRA_CHAVE", "")


def connection_string() -> str:
    return (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={AZURE_USER};"
        f"PWD={AZURE_PALAVRA_CHAVE};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )


def extrair_cae(registo: dict) -> str | None:
    cae = registo.get("cae")
    if isinstance(cae, list):
        return ",".join(str(c) for c in cae)
    if cae is not None:
        return str(cae)
    return None


def parse_date(val) -> date | None:
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return datetime.fromisoformat(str(val).replace("Z", "")).date()
    except (ValueError, TypeError):
        return None


def parse_capital(val) -> float | None:
    if not val:
        return None
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return None


def parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def mapear_registo(resultado: dict) -> dict:
    r = resultado.get("dados") or {}
    contactos = r.get("contacts") or {}
    estrutura = r.get("structure") or {}
    geo = r.get("geo") or {}
    place = r.get("place") or {}
    creditos = resultado.get("creditos") or {}
    creditos_left = creditos.get("left") or {}

    return {
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
    raw = sys.stdin.read()
    if not raw.strip():
        print("ERRO: Nenhum JSON recebido no stdin.", file=sys.stderr)
        sys.exit(1)

    try:
        resultado = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERRO: JSON inválido — {e}", file=sys.stderr)
        sys.exit(1)

    if resultado.get("erro"):
        print(f"ERRO na consulta: {resultado['erro']}", file=sys.stderr)
        sys.exit(1)

    nif = resultado.get("nif")
    if not nif:
        print("ERRO: NIF não encontrado no JSON", file=sys.stderr)
        sys.exit(1)

    reg = mapear_registo(resultado)

    if not AZURE_USER or not AZURE_PALAVRA_CHAVE:
        print("ERRO: AZURE_USER ou AZURE_PALAVRA_CHAVE não definidos no .env",
              file=sys.stderr)
        sys.exit(1)

    try:
        conn = pyodbc.connect(connection_string(), timeout=30)
        conn.autocommit = False
        cursor = conn.cursor()
    except pyodbc.Error as e:
        print(f"ERRO: Falha na ligação à BD — {e}", file=sys.stderr)
        sys.exit(1)

    cols = colunas_tabela()
    vals = valores_para_insert(reg)
    sql_insert_stg = (
        f"INSERT INTO {TABELA_STAGING} ({','.join(cols)}) "
        f"VALUES ({placeholders()})"
    )

    try:
        cursor.execute(sql_insert_stg, vals)
        print(f"NIF {nif} inserido em {TABELA_STAGING}.", file=sys.stderr)
        conn.commit()
    except pyodbc.Error as e:
        conn.rollback()
        print(f"ERRO: Falha na inserção — {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Importa o JSON do consulta_nif.py para uma base de dados SQLite local.

Cria automaticamente a base de dados e as tabelas se não existirem.

Uso:
    python consulta_nif.py 509442013 | python importar_nif_sqlite.py
    python importar_nif_sqlite.py < ficheiro.json

Se o NIF já existir na tabela nif_pt, insere em nif_pt_stg (staging).
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import date, datetime


DB_PATH = Path(__file__).parent / "data" / "nif_pt.db"


SQL_DDL = """
CREATE TABLE IF NOT EXISTS nif_pt (
    nif                     INTEGER PRIMARY KEY,
    nif_valido_formato      INTEGER,
    data_consulta           TEXT NOT NULL DEFAULT (datetime('now')),
    consulta_origem         TEXT DEFAULT 'nif.pt',

    seo_url                 TEXT,
    title                   TEXT,
    alias                   TEXT,
    status                  TEXT,
    start_date              TEXT,
    activity                TEXT,

    place_address           TEXT,
    place_pc4               TEXT,
    place_pc3               TEXT,
    place_city              TEXT,

    address                 TEXT,
    pc4                     TEXT,
    pc3                     TEXT,
    city                    TEXT,

    geo_region              TEXT,
    geo_county              TEXT,
    geo_parish              TEXT,

    contacts_email          TEXT,
    contacts_phone          TEXT,
    contacts_website        TEXT,
    contacts_fax            TEXT,

    structure_nature        TEXT,
    structure_capital       REAL,
    structure_capital_currency TEXT,

    cae                     TEXT,

    racius                  TEXT,
    portugalio              TEXT,

    creditos_used           TEXT,
    creditos_left_month     INTEGER,
    creditos_left_day       INTEGER,
    creditos_left_hour      INTEGER,
    creditos_left_minute    INTEGER,
    creditos_left_paid      INTEGER
);

CREATE TABLE IF NOT EXISTS nif_pt_stg (
    nif                     INTEGER NOT NULL,
    nif_valido_formato      INTEGER,
    data_consulta           TEXT NOT NULL DEFAULT (datetime('now')),
    consulta_origem         TEXT DEFAULT 'nif.pt',
    data_staging            TEXT NOT NULL DEFAULT (datetime('now')),
    processado              INTEGER NOT NULL DEFAULT 0,

    seo_url                 TEXT,
    title                   TEXT,
    alias                   TEXT,
    status                  TEXT,
    start_date              TEXT,
    activity                TEXT,

    place_address           TEXT,
    place_pc4               TEXT,
    place_pc3               TEXT,
    place_city              TEXT,

    address                 TEXT,
    pc4                     TEXT,
    pc3                     TEXT,
    city                    TEXT,

    geo_region              TEXT,
    geo_county              TEXT,
    geo_parish              TEXT,

    contacts_email          TEXT,
    contacts_phone          TEXT,
    contacts_website        TEXT,
    contacts_fax            TEXT,

    structure_nature        TEXT,
    structure_capital       REAL,
    structure_capital_currency TEXT,

    cae                     TEXT,

    racius                  TEXT,
    portugalio              TEXT,

    creditos_used           TEXT,
    creditos_left_month     INTEGER,
    creditos_left_day       INTEGER,
    creditos_left_hour      INTEGER,
    creditos_left_minute    INTEGER,
    creditos_left_paid      INTEGER,

    PRIMARY KEY (nif, data_staging)
);
"""


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Cria as tabelas se não existirem
    conn.executescript(SQL_DDL)
    conn.commit()
    return conn


def extrair_cae(registo: dict) -> str | None:
    cae = registo.get("cae")
    if isinstance(cae, list):
        return ",".join(str(c) for c in cae)
    if cae is not None:
        return str(cae)
    return None


def parse_date(val) -> str | None:
    if not val:
        return None
    try:
        d = datetime.fromisoformat(str(val).replace("Z", "")).date()
        return d.isoformat()
    except (ValueError, TypeError):
        return None


def parse_number(val, to_type=float):
    if not val:
        return None
    try:
        return to_type(str(val).replace(",", "."))
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
        "nif": parse_number(resultado.get("nif"), int),
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
        "structure_capital": parse_number(estrutura.get("capital")),
        "structure_capital_currency": estrutura.get("capital_currency"),
        "cae": extrair_cae(r),
        "racius": r.get("racius"),
        "portugalio": r.get("portugalio"),
        "creditos_used": creditos.get("used"),
        "creditos_left_month": parse_number(creditos_left.get("month"), int),
        "creditos_left_day": parse_number(creditos_left.get("day"), int),
        "creditos_left_hour": parse_number(creditos_left.get("hour"), int),
        "creditos_left_minute": parse_number(creditos_left.get("minute"), int),
        "creditos_left_paid": parse_number(creditos_left.get("paid"), int),
    }


COLUNAS = [
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

    conn = get_db()
    cursor = conn.cursor()

    placeholders = ",".join("?" for _ in COLUNAS)
    sql_insert = f"INSERT INTO nif_pt ({','.join(COLUNAS)}) VALUES ({placeholders})"
    sql_insert_stg = f"INSERT INTO nif_pt_stg ({','.join(COLUNAS)}) VALUES ({placeholders})"

    vals = [reg.get(c) for c in COLUNAS]

    try:
        cursor.execute("SELECT 1 FROM nif_pt WHERE nif = ?", (nif,))
        existe = cursor.fetchone()

        if existe:
            cursor.execute(sql_insert_stg, vals)
            print(
                f"NIF {nif} já existia em nif_pt. "
                f"Inserido em nif_pt_stg para staging.",
                file=sys.stderr,
            )
        else:
            cursor.execute(sql_insert, vals)
            print(f"NIF {nif} inserido em nif_pt.", file=sys.stderr)

        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"ERRO: Falha na inserção — {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()

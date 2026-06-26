#!/usr/bin/env python3
"""
Guarda o JSON do consulta_nif.py numa base de dados SQLite.

Cria automaticamente a base de dados e a tabela se não existir.

Uso:
    python consulta_nif.py 509442013 | python importar_nif_sqlite.py
    python importar_nif_sqlite.py < ficheiro.json

A configuração é lida do config.yaml via config.py.
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from config.config import get_config


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
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SQL_DDL)
    conn.commit()
    return conn


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

    conn = get_db()
    cursor = conn.cursor()

    try:
        dados_json = json.dumps(resultado, ensure_ascii=False)
        cursor.execute(
            f"INSERT INTO {TABELA} (nif, dados, data_consulta) VALUES (?, ?, ?)",
            (nif, dados_json, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        print(f"NIF {nif} guardado em {TABELA}.", file=sys.stderr)
    except sqlite3.Error as e:
        conn.rollback()
        print(f"ERRO: Falha na inserção — {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()

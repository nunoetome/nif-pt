#!/usr/bin/env python3
"""
Orquestrador de consultas NIF — lê NIFs de um Excel e consulta a API nif.pt
respeitando os limites de taxa (rate limits) definidos no config.yaml.

Uso:
    python orquestrador.py --input nifs.xlsx
    python orquestrador.py --input nifs.xlsx --azure --no-sqlite
    python orquestrador.py --input nifs.xlsx --resume
    python orquestrador.py --input nifs.xlsx --pause 120
"""

import argparse
import json
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from config.config import get_config
from consulta_nif import consultar_nif, validar_nif


cfg = get_config("orquestrador")

LIMITS = {
    "minuto": cfg.get("max_per_minute", 1),
    "hora": cfg.get("max_per_hour", 10),
    "dia": cfg.get("max_per_day", 100),
    "mes": cfg.get("max_per_month", 1000),
}
PAUSE_ON_LIMIT = cfg.get("pause_on_limit", 60)
INPUT_COLUNA = cfg.get("input_coluna", "nif")
OUTPUT_SQLITE_DEFAULT = cfg.get("output_sqlite", True)
OUTPUT_AZURE_DEFAULT = cfg.get("output_azure", False)

RAIZ = Path(__file__).parent
PROGRESSO_FILE = RAIZ / "data" / "orquestrador_progresso.json"

PERIODOS = {
    "minuto": 60,
    "hora": 3600,
    "dia": 86400,
    "mes": 2592000,
}


class RateLimiter:
    """Controla os limites de taxa por período (minuto, hora, dia, mês)."""

    def __init__(self, limits: dict[str, int], pause: int = 60):
        self.limits = {p: v for p, v in limits.items() if v > 0}
        self.pause = pause
        self.windows: dict[str, deque[float]] = {
            p: deque() for p in PERIODOS
        }
        self._all_timestamps: list[float] = []

    def restaurar(self, timestamps: list[float]):
        now = time.time()
        for ts in timestamps:
            for periodo, janela in self.windows.items():
                if now - ts < PERIODOS[periodo]:
                    janela.append(ts)
        if timestamps:
            logger.debug(
                f"Rate limiter restaurado: {sum(len(w) for w in self.windows.values())} "
                f"pedido(s) na janela"
            )

    def esperar_se_necessario(self):
        while True:
            now = time.time()
            max_wait = 0.0

            for periodo, janela in self.windows.items():
                limite = self.limits.get(periodo, 0)
                if limite <= 0:
                    continue
                cutoff = now - PERIODOS[periodo]
                while janela and janela[0] < cutoff:
                    janela.popleft()
                if len(janela) >= limite:
                    oldest = janela[0]
                    wait = oldest + PERIODOS[periodo] - now + 1
                    max_wait = max(max_wait, wait)

            if max_wait <= 0:
                return

            sleep_time = max(max_wait, min(float(self.pause), 5.0))
            logger.warning(
                f"[rate] Limite de taxa atingido. A aguardar {sleep_time:.0f}s..."
            )
            time.sleep(sleep_time)

    def registar_pedido(self):
        now = time.time()
        for janela in self.windows.values():
            janela.append(now)
        self._all_timestamps.append(now)

    @property
    def timestamps(self) -> list[float]:
        now = time.time()
        return [ts for ts in self._all_timestamps
                if now - ts < max(PERIODOS.values())]


def carregar_nifs(input_path: Path, coluna: str) -> list[str]:
    logger.info(f"A ler Excel: {input_path}")
    df = pd.read_excel(input_path)
    if coluna not in df.columns:
        logger.error(
            f"Coluna '{coluna}' não encontrada no Excel. "
            f"Colunas disponíveis: {list(df.columns)}"
        )
        sys.exit(1)
    nifs = df[coluna].dropna().astype(str).str.strip().tolist()
    validos = [n for n in nifs if n.isdigit() and len(n) == 9]
    invalidos = len(nifs) - len(validos)
    if invalidos:
        logger.warning(f"{invalidos} NIF(s) ignorado(s) por formato inválido")
    logger.info(f"{len(validos)} NIF(s) válido(s) carregados")
    return validos


def guardar_progresso(nifs_processados: set, rate_limiter: RateLimiter):
    dados = {
        "nifs_processados": sorted(nifs_processados),
        "timestamps": rate_limiter.timestamps,
        "atualizado_em": datetime.now().isoformat(),
    }
    PROGRESSO_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESSO_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def carregar_progresso() -> tuple[set, list]:
    if not PROGRESSO_FILE.exists():
        return set(), []
    with open(PROGRESSO_FILE, "r", encoding="utf-8") as f:
        dados = json.load(f)
    logger.info(
        f"Progresso carregado: {len(dados['nifs_processados'])} NIF(s) já processados"
    )
    return set(dados["nifs_processados"]), dados.get("timestamps", [])


def _inserir_sqlite(resultado: dict):
    try:
        from importar_nif_sqlite import get_db, TABELA
    except ImportError as e:
        logger.error(f"Erro ao importar módulo SQLite: {e}")
        return

    nif = resultado.get("nif")
    dados_json = json.dumps(resultado, ensure_ascii=False)
    data_consulta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    try:
        conn.execute(
            f"INSERT INTO {TABELA} (nif, dados, data_consulta) VALUES (?, ?, ?)",
            (nif, dados_json, data_consulta),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao inserir NIF {nif} no SQLite: {e}")
    finally:
        conn.close()


def _inserir_azure(resultado: dict):
    try:
        from importar_nif import (
            mapear_registo,
            colunas_tabela,
            valores_para_insert,
            connection_string,
            TABELA_STAGING,
        )
        import pyodbc
    except ImportError as e:
        logger.error(f"Erro ao importar dependências Azure SQL: {e}")
        return

    reg = mapear_registo(resultado)
    cols = colunas_tabela()
    vals = valores_para_insert(reg)
    placeholders = ",".join("?" for _ in cols)
    sql = (
        f"INSERT INTO {TABELA_STAGING} ({','.join(cols)}) "
        f"VALUES ({placeholders})"
    )

    try:
        conn = pyodbc.connect(connection_string(), timeout=30)
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute(sql, vals)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao inserir NIF {reg.get('nif')} na Azure: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Orquestrador de consultas NIF.pt — "
                    "lê NIFs de um Excel e consulta a API respeitando rate limits"
    )
    parser.add_argument(
        "--input", required=True,
        help="Caminho para o ficheiro Excel com os NIFs (coluna 'nif')"
    )
    parser.add_argument(
        "--sqlite", dest="sqlite", default=None, action="store_true",
        help="Guardar resultados em SQLite"
    )
    parser.add_argument(
        "--no-sqlite", dest="sqlite", action="store_false",
        help="Não guardar em SQLite"
    )
    parser.add_argument(
        "--azure", dest="azure", default=None, action="store_true",
        help="Guardar resultados em Azure SQL"
    )
    parser.add_argument(
        "--no-azure", dest="azure", action="store_false",
        help="Não guardar em Azure SQL"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Continuar de onde parou (usa progresso guardado)"
    )
    parser.add_argument(
        "--pause", type=int, default=None,
        help="Segundos de pausa quando limite é atingido (override config)"
    )
    args = parser.parse_args()

    usar_sqlite = args.sqlite if args.sqlite is not None else OUTPUT_SQLITE_DEFAULT
    usar_azure = args.azure if args.azure is not None else OUTPUT_AZURE_DEFAULT
    pause = args.pause if args.pause is not None else PAUSE_ON_LIMIT

    if not usar_sqlite and not usar_azure:
        logger.warning(
            "Nenhum output definido (--sqlite nem --azure). "
            "Os resultados serão apenas mostrados no log."
        )

    nifs = carregar_nifs(Path(args.input), INPUT_COLUNA)
    if not nifs:
        logger.error("Nenhum NIF válido encontrado no Excel.")
        sys.exit(1)

    rate_limiter = RateLimiter(LIMITS, pause)

    processados: set[str] = set()
    if args.resume:
        processados, timestamps = carregar_progresso()
        rate_limiter.restaurar(timestamps)
        pendentes = [n for n in nifs if n not in processados]
        logger.info(
            f"{len(processados)} já processados, "
            f"{len(pendentes)} pendentes de {len(nifs)} total"
        )
        nifs = pendentes

    total = len(nifs)
    erros = 0

    logger.info(f"A processar {total} NIF(s)")
    inicio = time.time()

    try:
        for idx, nif in enumerate(nifs, 1):
            logger.info(f"[{idx}/{total}] NIF: {nif}")

            if not validar_nif(nif):
                erros += 1
                logger.warning(f"NIF {nif}: inválido (digito de controlo errado) — a saltar")
                resultado = {
                    "nif": nif,
                    "valido": False,
                    "fonte": None,
                    "erro": "NIF inválido (digito de controlo errado)",
                    "dados": None,
                }
                processados.add(nif)
                guardar_progresso(processados, rate_limiter)
                continue

            rate_limiter.esperar_se_necessario()

            try:
                resultado = consultar_nif(nif)
            except Exception as e:
                logger.error(f"Erro na consulta do NIF {nif}: {e}")
                resultado = {
                    "nif": nif,
                    "valido": False,
                    "fonte": "nif.pt",
                    "erro": str(e),
                    "dados": None,
                }

            rate_limiter.registar_pedido()

            if resultado.get("erro"):
                erros += 1
                logger.warning(f"NIF {nif}: {resultado['erro']}")
            else:
                logger.info(f"NIF {nif}: OK")

            if usar_sqlite:
                _inserir_sqlite(resultado)
            if usar_azure:
                _inserir_azure(resultado)

            processados.add(nif)
            guardar_progresso(processados, rate_limiter)

    except KeyboardInterrupt:
        logger.info("[main] Interrompido pelo utilizador. A guardar progresso...")
        guardar_progresso(processados, rate_limiter)
        logger.info(f"[main] Progresso guardado: {len(processados)} NIF(s) processados")
        sys.exit(0)

    decorrido = time.time() - inicio
    logger.info("=" * 49)
    logger.info(f"{' Orquestração concluída ':=^49}")
    logger.info(f"  Total NIFs : {total}")
    logger.info(f"  Sucessos   : {total - erros}")
    logger.info(f"  Erros      : {erros}")
    logger.info(f"  Tempo total: {decorrido:.2f}s")
    logger.info("=" * 49)

    if PROGRESSO_FILE.exists():
        PROGRESSO_FILE.unlink()
        logger.info("Ficheiro de progresso removido (execução concluída).")


if __name__ == "__main__":
    main()

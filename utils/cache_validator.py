#!/usr/bin/env python3
"""
utils.cache_validator — Validação cache SQLite antes de pedir à API nif.pt.

Evita consumo de créditos repetindo pedidos para NIFs já consultados
recentemente. Consulta ``nif_pt`` (SQLite WAL) e, se o NIF existir com
``data_consulta`` dentro da janela ``cache_antiguidade_dias``, considera
recente e regista a tentativa em ``nif_ignorados`` sem ir à API.

Configuração (``config/config.yaml`` bloco ``default``):

* ``cache_ativo`` (bool, default ``true``) — liga/desliga a validação.
* ``cache_antiguidade_dias`` (int, default ``30``) — janela de recenticidade.
* ``cache_tabela_ignorados`` (str, default ``"nif_ignorados"``).

Tabelas SQLite (``data/nif_pt.db``):

* ``nif_pt`` — criada por :mod:`importar_nif_sqlite` (``id, nif, dados,
  data_consulta, run_id``).
* ``nif_ignorados`` — criada aqui (``id, nif, data_tentativa,
  data_ultima_consulta, dias_desde_ultima, motivo``).

Uso
---
>>> from utils.cache_validator import is_nif_recente, registar_ignorado, init_cache_tables
>>> init_cache_tables()
>>> recente, data_ult = is_nif_recente("509442013", dias=30)

See Also:
    :mod:`consulta_nif`, :mod:`importar_nif_sqlite`,
    :mod:`utils.error_handler` (padrão idempotente similar)
"""

import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# --- DDL -------------------------------------------------------------------

DDL_IGNORADOS = """
CREATE TABLE IF NOT EXISTS nif_ignorados (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    nif                     INTEGER NOT NULL,
    data_tentativa          TEXT NOT NULL DEFAULT (datetime('now')),
    data_ultima_consulta    TEXT,
    dias_desde_ultima       INTEGER,
    motivo                  TEXT NOT NULL DEFAULT 'cache_recente'
);
"""

DDL_IGNORADOS_IDX_NIF = "CREATE INDEX IF NOT EXISTS idx_nif_ignorados_nif ON nif_ignorados(nif);"
DDL_IGNORADOS_IDX_DATA = "CREATE INDEX IF NOT EXISTS idx_nif_ignorados_data ON nif_ignorados(data_tentativa);"

# --- Helpers config / DB ----------------------------------------------------


def _get_config() -> dict:
    """Lê configuração cache via :func:`config.config.get_config`.

    Returns:
        Dict de ``get_config("consulta_nif")`` ou ``{}`` se falhar
        (nunca levanta).

    Examples:
        >>> isinstance(_get_config(), dict)
        True
    """
    try:
        from config.config import get_config

        cfg = get_config("consulta_nif")
        return cfg
    except Exception as e:
        logger.warning("[cache] Falha a ler config: %s", e)
        return {}


def _get_db_path() -> Path:
    """Resolve caminho absoluto de ``data/nif_pt.db`` a partir do config.

    Returns:
        ``Path`` absoluto (``data/nif_pt.db`` por defeito).

    Examples:
        >>> _get_db_path().name
        'nif_pt.db'
    """
    cfg = _get_config()
    db_path_cfg = cfg.get("db_path", "data/nif_pt.db")
    raiz = Path(__file__).resolve().parent.parent
    p = Path(db_path_cfg)
    if not p.is_absolute():
        p = raiz / p
    return p


def _get_cache_config() -> tuple[bool, int, str]:
    """Devolve tuplo cache a partir do config.yaml.

    Returns:
        ``(cache_ativo, cache_antiguidade_dias, cache_tabela_ignorados)``.

    Examples:
        >>> ativo, dias, tabela = _get_cache_config()
        >>> isinstance(ativo, bool)
        True
    """
    cfg = _get_config()
    ativo = bool(cfg.get("cache_ativo", True))
    # aceita bool/int/str; normaliza
    try:
        dias = int(cfg.get("cache_antiguidade_dias", 30))
    except Exception:
        dias = 30
    tabela = str(cfg.get("cache_tabela_ignorados", "nif_ignorados") or "nif_ignorados")
    # sanitiza nome tabela (só alfanum + _)
    if not tabela.replace("_", "").isalnum():
        tabela = "nif_ignorados"
    return ativo, dias, tabela


def _get_connection() -> sqlite3.Connection:
    """Abre ligação SQLite WAL e garante DDL de ``nif_ignorados``.

    Returns:
        ``sqlite3.Connection`` aberta com ``journal_mode=WAL`` e
        ``DDL_IGNORADOS`` + índices garantidos.

    Examples:
        >>> conn = _get_connection()  # doctest: +SKIP
        >>> conn.close()  # doctest: +SKIP
    """
    db_path = _get_db_path()
    logger.debug("[cache] DB_PATH=%s", db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("PRAGMA journal_mode=WAL")
        row = cur.fetchone()
        logger.debug("[cache] PRAGMA WAL -> %s", row[0] if row else "wal")
    except sqlite3.Error as e:
        logger.warning("[cache] Falha PRAGMA WAL: %s", e)
    try:
        _, _, tabela = _get_cache_config()
        # DDL usa nome fixo nif_ignorados; se config divergir, usa template
        ddl = DDL_IGNORADOS.replace("nif_ignorados", tabela) if tabela != "nif_ignorados" else DDL_IGNORADOS
        idx_nif = DDL_IGNORADOS_IDX_NIF.replace("nif_ignorados", tabela) if tabela != "nif_ignorados" else DDL_IGNORADOS_IDX_NIF
        idx_data = DDL_IGNORADOS_IDX_DATA.replace("nif_ignorados", tabela) if tabela != "nif_ignorados" else DDL_IGNORADOS_IDX_DATA
        conn.executescript(ddl)
        conn.execute(idx_nif)
        conn.execute(idx_data)
        conn.commit()
        logger.debug("[cache] DDL %s garantido", tabela)
    except sqlite3.Error as e:
        logger.warning("[cache] Falha DDL nif_ignorados: %s", e)
    return conn


def init_cache_tables() -> None:
    """Garante que a tabela ``nif_ignorados`` existe (idempotente).

    Abre ligação via :func:`_get_connection` (que já executa DDL) e fecha
    imediatamente. Chamado no arranque de :func:`consulta_nif.main`.

    Returns:
        ``None`` — efeito colateral é criação da tabela se faltar.

    Examples:
        >>> init_cache_tables()  # doctest: +SKIP
    """
    logger.debug(f"{' init_cache_tables() ':~^49}")
    t = time.perf_counter()
    conn = _get_connection()
    try:
        conn.close()
        logger.debug("[cache] init_cache_tables() -> %.2fs", time.perf_counter() - t)
    except Exception:
        pass


# --- Parsers ---------------------------------------------------------------


def _parse_data_consulta(val: str | None) -> datetime | None:
    """Converte ``data_consulta`` da BD para ``datetime``.

    Aceita ``YYYY-MM-DD HH:MM:SS`` (de ``importar_nif_sqlite.py:223``) e
    ISO ``YYYY-MM-DDTHH:MM:SS`` / com ``Z``.

    Args:
        val: Valor de ``data_consulta`` (str ou None).

    Returns:
        ``datetime`` ou ``None`` se vazio/inválido.

    Examples:
        >>> _parse_data_consulta("2026-09-10 12:00:00") is not None
        True
        >>> _parse_data_consulta(None) is None
        True
    """
    if not val:
        return None
    s = str(val).strip()
    # tenta formatos conhecidos
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        # fallback fromisoformat com Z
        return datetime.fromisoformat(s.replace("Z", "").replace("T", " "))
    except Exception:
        return None


# --- API pública -----------------------------------------------------------


def is_nif_recente(nif: str | int, dias: int | None = None) -> tuple[bool, str | None]:
    """Verifica se o NIF já existe em ``nif_pt`` dentro da janela ``dias``.

    Pesquisa ``SELECT data_consulta FROM nif_pt WHERE nif=? ORDER BY
    datetime(data_consulta) DESC LIMIT 1`` e compara com ``now - timedelta(dias)``.

    Args:
        nif: NIF a pesquisar (str ou int com 9 dígitos).
        dias: Janela de recenticidade em dias. Se ``None`` lê
            ``cache_antiguidade_dias`` do ``config.yaml`` (default ``30``).

    Returns:
        Tuplo ``(recente: bool, data_ultima_consulta: str | None)``.
        ``recente`` é ``True`` se existir registo com
        ``data_ultima >= now - dias``. ``data_ultima`` é ISO
        ``YYYY-MM-DD HH:MM:SS`` da linha mais recente, ou ``None`` se sem registo.
        Falhas de BD devolvem ``(False, None)`` (fail-open).

    Examples:
        >>> is_nif_recente("999999999", dias=30)  # doctest: +SKIP
        (False, None)

    Notas:
        * ``data_consulta`` pode vir em ``%Y-%m-%d %H:%M:%S`` ou ISO; ambos são parseados.
        * TAG ``[cache]`` + TIMING (R9).
    """
    logger.debug(f"{' is_nif_recente() ':~^49}")
    t = time.perf_counter()
    if dias is None:
        _, dias_cfg, _ = _get_cache_config()
        dias = dias_cfg
    try:
        dias = int(dias)
    except Exception:
        dias = 30
    if dias <= 0:
        logger.debug("[cache] dias=%s <=0 -> nunca recente", dias)
        return False, None

    try:
        nif_int = int(str(nif).strip())
    except Exception:
        logger.debug("[cache] NIF inválido '%s' -> não recente", nif)
        return False, None

    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        # verifica se tabela nif_pt existe
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nif_pt'")
        if not cur.fetchone():
            logger.debug("[cache] tabela nif_pt inexistente -> não recente")
            return False, None
        cur.execute(
            "SELECT data_consulta FROM nif_pt WHERE nif=? ORDER BY datetime(data_consulta) DESC LIMIT 1",
            (nif_int,),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            logger.debug("[cache] NIF %s sem registo em nif_pt -> não recente (%.2fs)", nif, time.perf_counter() - t)
            return False, None
        data_str = str(row[0])
        dt_ultima = _parse_data_consulta(data_str)
        if not dt_ultima:
            logger.warning("[cache] Falha parse data_ultima '%s' nif=%s -> não recente", data_str, nif)
            return False, None
        agora = datetime.now()
        diff = agora - dt_ultima
        # diff.days pode ser negativo se relógio futuro; tratar como recente
        dias_desde = diff.days
        # também considera horas: se diff total < dias*24h, é recente mesmo que days=0
        # usar total_seconds para precisão
        total_dias = diff.total_seconds() / 86400
        recente = total_dias < dias and total_dias >= 0
        # se total_dias negativo (data futura), considera recente por segurança
        if total_dias < 0:
            recente = True
            dias_desde = 0
        logger.info(
            "[cache] NIF %s ultima=%s dias_desde=%d antiguidade=%d recente=%s (%.2fs)",
            nif,
            data_str,
            dias_desde,
            dias,
            recente,
            time.perf_counter() - t,
        )
        logger.debug("[cache] is_nif_recente(%s) -> %s (%.2fs)", nif, recente, time.perf_counter() - t)
        return recente, data_str
    except sqlite3.Error as e:
        logger.warning("[cache] Falha consulta recenticidade nif=%s: %s", nif, e)
        return False, None
    except Exception as e:
        logger.warning("[cache] Erro inesperado is_nif_recente nif=%s: %s", nif, e)
        return False, None
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def registar_ignorado(
    nif: str | int,
    data_ultima_consulta: str | None,
    motivo: str = "cache_recente",
) -> int | None:
    """Regista tentativa ignorada em ``nif_ignorados``.

    Insere ``nif, data_ultima_consulta, dias_desde_ultima, motivo`` com
    ``data_tentativa = datetime('now')`` (DEFAULT). Calcula
    ``dias_desde_ultima`` a partir de ``data_ultima_consulta`` se possível.

    Args:
        nif: NIF ignorado (str ou int).
        data_ultima_consulta: ``data_consulta`` da linha mais recente em
            ``nif_pt`` (ISO ``YYYY-MM-DD HH:MM:SS``) ou ``None``.
        motivo: Motivo do ignorado (default ``"cache_recente"``).

    Returns:
        ``id`` (``lastrowid``) do registo inserido ou ``None`` se falhar
        (logado com ``[cache] Falha ao registar``).

    Examples:
        >>> registar_ignorado("509442013", "2026-09-10 12:00:00")  # doctest: +SKIP
        1
    """
    logger.debug(f"{' registar_ignorado() ':~^49}")
    t = time.perf_counter()
    try:
        nif_int = int(str(nif).strip())
    except Exception:
        logger.warning("[cache] NIF inválido para registar_ignorado: %s", nif)
        return None

    dias_desde: int | None = None
    if data_ultima_consulta:
        dt = _parse_data_consulta(data_ultima_consulta)
        if dt:
            try:
                diff = datetime.now() - dt
                dias_desde = diff.days if diff.days >= 0 else 0
            except Exception:
                dias_desde = None

    _, _, tabela = _get_cache_config()
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        # usa nome de tabela sanitizado
        cur.execute(
            f"INSERT INTO {tabela} (nif, data_ultima_consulta, dias_desde_ultima, motivo) VALUES (?, ?, ?, ?)",
            (nif_int, data_ultima_consulta, dias_desde, motivo),
        )
        conn.commit()
        row_id = cur.lastrowid
        logger.info(
            "[cache] Ignorado registado id=%s nif=%s ultima=%s dias_desde=%s (%.2fs)",
            row_id,
            nif,
            data_ultima_consulta,
            dias_desde,
            time.perf_counter() - t,
        )
        return row_id
    except sqlite3.Error as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        logger.error("[cache] Falha ao registar ignorado nif=%s: %s", nif, e)
        return None
    finally:
        try:
            if conn:
                cur.close()
                conn.close()
        except Exception:
            pass

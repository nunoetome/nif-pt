#!/usr/bin/env python3
"""
utils.error_handler — Camada de tratamento de erros da API nif.pt.

Responsabilidades:
  - parse do JSON de resposta para decidir tipo de erro
  - persistência do erro em tabela `nif_api_erros` (SQLite local)
  - decisão de ação por tipo: retry com espera vs abort

Tipos suportados (extensível):
  - rate_limit_minute  -> guarda + espera tempo_espera_minuto (default 60s) + retry
  - rate_limit_hour    -> guarda + espera tempo_espera_hora   (default 3600s) + retry
  - rate_limit_day     -> guarda + encerra app em erro (log)
  - rate_limit_month   -> guarda + encerra app em erro (log)
  - rate_limit_paid    -> guarda + encerra (sem créditos pagos)
  - unknown / generic  -> guarda + devolve erro sem retry automático

Configuração em config.yaml (bloco default):
  tempo_espera_minuto: 60
  tempo_espera_hora: 3600

Tabela SQLite `nif_api_erros`:
  id, nif, data_erro, tipo_erro, codigo_erro, mensagem,
  left_month/day/hour/minute/paid, dados_json, acao, resolvido

Uso:
  from utils.error_handler import classificar_erro, tratar_erro, guardar_erro, init_error_table

  tipo = classificar_erro(data)
  resultado = tratar_erro(nif, data, attempt, retry_count)
  # resultado = {"tipo": ..., "acao": "retry"|"abort"|"none", "espera": int, "deve_retry": bool}

Extensibilidade:
  Adicionar novos `elif` em classificar_erro() e novo ramo em tratar_erro().
"""

import json
import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# --- DDL SQLite --------------------------------------------------------------
DDL_ERROS = """
CREATE TABLE IF NOT EXISTS nif_api_erros (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nif             INTEGER,
    data_erro       TEXT NOT NULL DEFAULT (datetime('now')),
    tipo_erro       TEXT NOT NULL,
    codigo_erro     TEXT,
    mensagem        TEXT,
    left_month      INTEGER,
    left_day        INTEGER,
    left_hour       INTEGER,
    left_minute     INTEGER,
    left_paid       INTEGER,
    dados_json      TEXT NOT NULL,
    acao            TEXT,
    run_id          TEXT,
    resolvido       INTEGER NOT NULL DEFAULT 0
);
"""

DDL_ERROS_INDEX = "CREATE INDEX IF NOT EXISTS idx_nif_api_erros_nif ON nif_api_erros(nif);"
DDL_ERROS_INDEX_TIPO = "CREATE INDEX IF NOT EXISTS idx_nif_api_erros_tipo ON nif_api_erros(tipo_erro);"
DDL_ERROS_INDEX_RUNID = "CREATE INDEX IF NOT EXISTS idx_nif_api_erros_run_id ON nif_api_erros(run_id);"

# --- Tipos de erro (constantes) ----------------------------------------------
TIPO_RATE_LIMIT_MINUTE = "rate_limit_minute"
TIPO_RATE_LIMIT_HOUR = "rate_limit_hour"
TIPO_RATE_LIMIT_DAY = "rate_limit_day"
TIPO_RATE_LIMIT_MONTH = "rate_limit_month"
TIPO_RATE_LIMIT_PAID = "rate_limit_paid"
TIPO_UNKNOWN = "unknown"
TIPO_GENERIC_ERROR = "generic_error"

# --- Helpers config / DB -----------------------------------------------------

def _get_config() -> dict:
    """Lê configuração de resiliência via :func:`config.config.get_config`.

    Returns:
        Dict de ``get_config("consulta_nif")`` ou ``{}`` se falhar
        (nunca levanta — usado por :func:`get_tempo_espera` e
        :func:`get_max_tentativas`).

    Examples:
        >>> isinstance(_get_config(), dict)
        True
    """
    try:
        from config.config import get_config
        cfg = get_config("consulta_nif")
        return cfg
    except Exception as e:
        logger.warning("[erro] Falha a ler config para error_handler: %s", e)
        return {}


def _get_db_path() -> Path:
    """Resolve o caminho absoluto de ``data/nif_pt.db`` a partir do config.

    Returns:
        ``Path`` absoluto para a BD SQLite (``data/nif_pt.db`` por defeito).

    Examples:
        >>> _get_db_path().name
        'nif_pt.db'
    """
    cfg = _get_config()
    # importar_nif_sqlite usa cfg.get("db_path") relativo à raiz do projeto
    db_path_cfg = cfg.get("db_path", "data/nif_pt.db")
    # config está em config/config.py -> parent.parent é raiz
    raiz = Path(__file__).resolve().parent.parent
    p = Path(db_path_cfg)
    if not p.is_absolute():
        p = raiz / p
    return p


def _get_connection() -> sqlite3.Connection:
    """Abre ligação SQLite com WAL e garante DDL de ``nif_api_erros``.

    Returns:
        ``sqlite3.Connection`` aberta com ``journal_mode=WAL`` e
        ``DDL_ERROS`` + índices garantidos.

    Examples:
        >>> conn = _get_connection()  # doctest: +SKIP
        >>> conn.close()  # doctest: +SKIP
    """
    db_path = _get_db_path()
    logger.debug("[erro] DB_PATH=%s", db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("PRAGMA journal_mode=WAL")
        row = cur.fetchone()
        logger.debug("[erro] PRAGMA WAL -> %s", row[0] if row else "wal")
    except sqlite3.Error as e:
        logger.warning("[erro] Falha PRAGMA WAL: %s", e)
    # garante tabela
    try:
        conn.executescript(DDL_ERROS)
        conn.execute(DDL_ERROS_INDEX)
        conn.execute(DDL_ERROS_INDEX_TIPO)
        try:
            conn.execute(DDL_ERROS_INDEX_RUNID)
        except sqlite3.Error:
            pass
        # migração idempotente para BDs antigas sem run_id
        try:
            cur = conn.execute("PRAGMA table_info(nif_api_erros)")
            cols = [r[1] for r in cur.fetchall()]
            if "run_id" not in cols:
                conn.execute("ALTER TABLE nif_api_erros ADD COLUMN run_id TEXT")
                conn.commit()
                logger.info("[erro] Migração: coluna run_id adicionada a nif_api_erros")
        except sqlite3.Error as me:
            logger.debug("[erro] Migração run_id ignorada: %s", me)
        conn.commit()
        logger.debug("[erro] DDL nif_api_erros garantido")
    except sqlite3.Error as e:
        logger.warning("[erro] Falha DDL nif_api_erros: %s", e)
    return conn


def init_error_table() -> None:
    """Garante que a tabela ``nif_api_erros`` existe (idempotente).

    Abre ligação via :func:`_get_connection` (que já executa ``DDL_ERROS``)
    e fecha imediatamente. Chamado no arranque de :func:`consulta_nif.main`
    antes de qualquer request.

    Returns:
        ``None`` — efeito colateral é criação da tabela se faltar.

    Examples:
        >>> init_error_table()  # doctest: +SKIP
        >>> # tabela garantida em data/nif_pt.db
    """
    logger.debug(f"{' init_error_table() ':~^49}")
    t = time.perf_counter()
    conn = _get_connection()
    try:
        conn.close()
        logger.debug("[erro] init_error_table() -> %.2fs", time.perf_counter() - t)
    except Exception:
        pass


# --- Classificação -----------------------------------------------------------

def classificar_erro(data: dict) -> str:
    """
    Faz parse do JSON de resposta da API e decide que tipo de erro é.

    data: dict da API (ex: {"result":"error","message":"Limit per minute...","credits":{"left":{...}}})
    Retorna uma das constantes TIPO_*
    """
    logger.debug(f"{' classificar_erro() ':~^49}")
    if not isinstance(data, dict):
        logger.debug("[erro] classificar_erro dados não dict -> %s", type(data))
        return TIPO_UNKNOWN

    result = str(data.get("result", "") or "").lower()
    message = str(data.get("message", "") or data.get("erro", "") or "")
    message_lower = message.lower()

    # credits.left pode estar em data["credits"]["left"] ou direto em data["left"]
    credits = data.get("credits", {}) if isinstance(data.get("credits"), dict) else {}
    left = credits.get("left", {}) if isinstance(credits.get("left"), dict) else {}
    # fallback: left direto no root (caso do enunciado)
    if not left and isinstance(data.get("left"), dict):
        left = data.get("left")

    logger.debug("[erro] classificar result='%s' message='%s' left=%s", result, message[:120], left)

    # Só tratamos como rate-limit se result == error e mensagem contém limit
    # (ou left com 0 em alguma janela)
    is_error = result == "error" or "limit" in message_lower or "limit" in result

    if not is_error:
        # pode ser outro erro genérico da API (ex: nif inválido)
        if result not in ("success", ""):
            return TIPO_GENERIC_ERROR
        return TIPO_UNKNOWN

    # Prioridade: mensagem explícita
    if "limit per minute" in message_lower:
        return TIPO_RATE_LIMIT_MINUTE
    if "limit per hour" in message_lower:
        return TIPO_RATE_LIMIT_HOUR
    if "limit per day" in message_lower:
        return TIPO_RATE_LIMIT_DAY
    if "limit per month" in message_lower:
        return TIPO_RATE_LIMIT_MONTH
    if "limit per" in message_lower and "paid" in message_lower:
        return TIPO_RATE_LIMIT_PAID

    # Fallback genérico "Limit per" mas sem janela explícita — inferir via left
    if "limit per" in message_lower or "limit" in message_lower:
        # se só existe 1 janela a 0, inferimos essa
        try:
            if isinstance(left, dict):
                minute = left.get("minute")
                hour = left.get("hour")
                day = left.get("day")
                month = left.get("month")
                # paid esgotado?
                paid = left.get("paid")
                if minute == 0 and hour != 0 and day != 0 and month != 0:
                    return TIPO_RATE_LIMIT_MINUTE
                if hour == 0:
                    return TIPO_RATE_LIMIT_HOUR
                if day == 0:
                    return TIPO_RATE_LIMIT_DAY
                if month == 0:
                    return TIPO_RATE_LIMIT_MONTH
                if paid == 0 and "paid" in message_lower:
                    return TIPO_RATE_LIMIT_PAID
        except Exception as e:
            logger.debug("[erro] inferência left falhou: %s", e)
        # sem left útil -> genérico, assumir minuto por segurança? Não, marcar unknown rate-limit
        return TIPO_GENERIC_ERROR

    return TIPO_UNKNOWN


def get_tempo_espera(tipo_erro: str) -> int:
    """Devolve tempo de espera em segundos para o tipo, lido do ``config.yaml``.

    Args:
        tipo_erro: Uma das constantes ``TIPO_*`` (ex. ``rate_limit_minute``).

    Returns:
        ``60`` para ``minute`` (``tempo_espera_minuto``), ``3600`` para ``hour``
        (``tempo_espera_hora``), ``0`` para ``day/month/paid/unknown``
        (abort sem espera, lido de ``tempo_de_espera`` como fallback).

    Examples:
        >>> get_tempo_espera("rate_limit_minute") in (60, 0)  # doctest: +SKIP
        True
    """
    cfg = _get_config()
    if tipo_erro == TIPO_RATE_LIMIT_MINUTE:
        return int(cfg.get("tempo_espera_minuto", cfg.get("tempo_de_espera", 60)))
    if tipo_erro == TIPO_RATE_LIMIT_HOUR:
        return int(cfg.get("tempo_espera_hora", 3600))
    # day/month não têm espera (abort)
    return 0


def get_max_tentativas(tipo_erro: str) -> int:
    """Devolve número máximo de tentativas para o tipo, lido do ``config.yaml``.

    Args:
        tipo_erro: Constante ``TIPO_*``.

    Returns:
        ``max_tentativas_minuto`` (default ``3``) para minute,
        ``max_tentativas_hora`` (``2``) para hour,
        ``0`` para ``day/month/paid`` (abort imediato),
        ``max_tentativas_generico`` (``0``) para ``unknown/generic``.
        Fallback para ``retry_count`` se chave não existir.

    Examples:
        >>> get_max_tentativas("rate_limit_minute") >= 0
        True
    """
    cfg = _get_config()
    # fallback para retry_count se nova chave não existir (compat)
    if tipo_erro == TIPO_RATE_LIMIT_MINUTE:
        return int(cfg.get("max_tentativas_minuto", cfg.get("retry_count", 1)))
    if tipo_erro == TIPO_RATE_LIMIT_HOUR:
        return int(cfg.get("max_tentativas_hora", 1))
    if tipo_erro == TIPO_RATE_LIMIT_DAY:
        return int(cfg.get("max_tentativas_dia", 0))
    if tipo_erro == TIPO_RATE_LIMIT_MONTH:
        return int(cfg.get("max_tentativas_mes", 0))
    if tipo_erro == TIPO_RATE_LIMIT_PAID:
        return int(cfg.get("max_tentativas_paid", 0))
    # genérico / unknown — sem retry por defeito
    return int(cfg.get("max_tentativas_generico", 0))


def get_max_tentativas_global() -> int:
    """Devolve limite global de tentativas falhadas (``max_tentativas_global``).

    Returns:
        ``int`` de ``config.yaml`` (default ``5``, fallback ``retry_count``).

    Examples:
        >>> get_max_tentativas_global() >= 1
        True
    """
    cfg = _get_config()
    return int(cfg.get("max_tentativas_global", cfg.get("retry_count", 1)))


# --- Persistência ------------------------------------------------------------

def _safe_int(v) -> int | None:
    """Converte para ``int`` sem levantar; ``None`` ou falha → ``None``.

    Args:
        v: Valor a converter (``left.*`` pode ser ``None`` ou string).

    Returns:
        ``int`` ou ``None``.

    Examples:
        >>> _safe_int("5")
        5
        >>> _safe_int(None) is None
        True
    """
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def guardar_erro(
    nif: str | int | None,
    tipo_erro: str,
    codigo_erro: str | None,
    mensagem: str | None,
    left: dict | None,
    dados_completos: dict,
    acao: str | None = None,
    run_id: str | None = None,
) -> int | None:
    """Guarda o erro na tabela ``nif_api_erros`` (SQLite, WAL).

    Persiste ``nif``, ``tipo_erro``, ``codigo_erro`` (``result`` da API),
    ``mensagem`` (``message``), ``left_*`` (``credits.left``), ``dados_json``
    (payload completo), ``acao`` (``retry_60s`` / ``abort_day`` / ``none``),
    ``run_id`` (identificador da execução) e ``resolvido=0``.

    Args:
        nif: NIF consultado (str ou int; ``None`` → ``NULL``).
        tipo_erro: Constante ``TIPO_*`` de :func:`classificar_erro`.
        codigo_erro: ``data["result"]`` (ex. ``"error"``).
        mensagem: ``data["message"]`` truncável a 500 chars no DDL Azure.
        left: ``data["credits"]["left"]`` (dict ou ``None``/``[]``).
        dados_completos: Payload completo da API (serializado para JSON).
        acao: ``"retry_60s"`` / ``"retry_3600s"`` / ``"abort_day"`` / ``"none"``.
        run_id: Identificador da execução (``utils.run_id``). Se ``None``
            tenta resolver via ``get_run_id()``.

    Returns:
        ``id`` (``lastrowid``) do registo inserido ou ``None`` se falhar
        (logado com ``[erro] Falha ao guardar`` e ``rollback``).

    Examples:
        >>> guardar_erro("509442013", "rate_limit_minute", "error", "Limit per minute", {"minute": 0}, {"result": "error"})  # doctest: +SKIP
        1
    """
    logger.debug(f"{' guardar_erro() ':~^49}")
    t = time.perf_counter()
    try:
        dados_json = json.dumps(dados_completos, ensure_ascii=False)
    except Exception as e:
        logger.warning("[erro] Falha json.dumps dados_completos: %s", e)
        dados_json = str(dados_completos)

    left = left or {}
    # left pode ser lista vazia no free plan
    if isinstance(left, list):
        left = {}

    # nif pode vir como string; guardar como int se possível
    try:
        nif_int = int(str(nif)) if nif is not None else None
    except Exception:
        nif_int = None

    # run_id — tenta contexto se não fornecido
    if run_id is None:
        try:
            from utils.run_id import get_run_id
            run_id = get_run_id()
        except Exception:
            run_id = None

    conn = _get_connection()
    try:
        cur = conn.cursor()
        # Tenta com run_id; fallback sem coluna para BDs antigas
        try:
            cur.execute(
                """
                INSERT INTO nif_api_erros
                    (nif, tipo_erro, codigo_erro, mensagem,
                     left_month, left_day, left_hour, left_minute, left_paid,
                     dados_json, acao, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nif_int,
                    tipo_erro,
                    codigo_erro,
                    mensagem,
                    _safe_int(left.get("month")),
                    _safe_int(left.get("day")),
                    _safe_int(left.get("hour")),
                    _safe_int(left.get("minute")),
                    _safe_int(left.get("paid")),
                    dados_json,
                    acao,
                    run_id,
                ),
            )
        except sqlite3.OperationalError as oe:
            if "run_id" in str(oe).lower() or "no column named run_id" in str(oe).lower():
                logger.debug("[erro] Fallback sem run_id (coluna em falta): %s", oe)
                cur.execute(
                    """
                    INSERT INTO nif_api_erros
                        (nif, tipo_erro, codigo_erro, mensagem,
                         left_month, left_day, left_hour, left_minute, left_paid,
                         dados_json, acao)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        nif_int,
                        tipo_erro,
                        codigo_erro,
                        mensagem,
                        _safe_int(left.get("month")),
                        _safe_int(left.get("day")),
                        _safe_int(left.get("hour")),
                        _safe_int(left.get("minute")),
                        _safe_int(left.get("paid")),
                        dados_json,
                        acao,
                    ),
                )
            else:
                raise
        conn.commit()
        row_id = cur.lastrowid
        logger.info(
            "[erro] Erro guardado id=%s nif=%s tipo=%s acao=%s run_id=%s em %.2fs",
            row_id,
            nif,
            tipo_erro,
            acao,
            (run_id[:8] + "...") if run_id else "—",
            time.perf_counter() - t,
        )
        return row_id
    except sqlite3.Error as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("[erro] Falha ao guardar erro nif=%s tipo=%s: %s", nif, tipo_erro, e)
        return None
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# --- Dispatcher principal ----------------------------------------------------

def tratar_erro(
    nif: str,
    data: dict,
    attempt: int = 0,
    retry_count: int = 1,
    tentativas_por_tipo: dict | None = None,
    tentativa_global: int | None = None,
    run_id: str | None = None,
) -> dict:
    """
    Ponto de entrada principal da camada de tratamento de erros.

    Recebe a mensagem de erro (dict da API), decide tipo, persiste e
    devolve instrução de ação. Suporta limites por tipo + global.

    Args:
        nif: NIF consultado
        data: dict da API (result/message/credits)
        attempt: índice da tentativa atual (legado, 0-based) — usado se
                 tentativas_por_tipo/tentativa_global não forem fornecidos
        retry_count: max retries legado — fallback se novos limites não existirem
        tentativas_por_tipo: dict {tipo: count} com contagem já efetuada por tipo
                             (excluindo a atual). Se None, usa lógica legada.
        tentativa_global: índice global de tentativas falhadas (0-based). Se None,
                          usa `attempt`.

    Returns:
        {
          "tipo": str,            # TIPO_*
          "acao": "retry"|"abort"|"none",
          "espera": int,          # segundos a esperar (0 se abort/none)
          "deve_retry": bool,     # True se deve fazer retry
          "mensagem": str,
          "codigo": str,
          "max_tipo": int,        # limite por tipo usado
          "max_global": int,      # limite global usado
          "tentativas_tipo": int, # contagem atual do tipo
          "tentativa_global": int
        }
    Para tipos day/month, o chamador deve encerrar a app (sys.exit(1))
    após este retorno — a função já logou e persistiu.
    """
    logger.debug(f"{' tratar_erro() ':~^49}")
    t = time.perf_counter()

    tipo = classificar_erro(data)
    codigo = str(data.get("result", "") or "")
    mensagem = str(data.get("message", "") or data.get("erro", "") or codigo)

    credits = data.get("credits", {}) if isinstance(data.get("credits"), dict) else {}
    left = credits.get("left", {}) if isinstance(credits.get("left"), dict) else {}
    if not left and isinstance(data.get("left"), dict):
        left = data.get("left")
    if isinstance(left, list):
        left = {}

    # run_id resolve (contexto se não passado)
    if run_id is None:
        try:
            from utils.run_id import get_run_id
            run_id = get_run_id()
        except Exception:
            run_id = None

    logger.info("[erro] Tipo classificado nif=%s tipo=%s codigo='%s' msg='%.120s' run_id=%s", nif, tipo, codigo, mensagem, (run_id[:8] + "...") if run_id else "—")

    # Helpers — limites por tipo + global (novo) vs legado
    modo_novo = tentativas_por_tipo is not None or tentativa_global is not None
    if modo_novo:
        max_tipo = get_max_tentativas(tipo)
        max_global = get_max_tentativas_global()
        tenta_tipo = (tentativas_por_tipo or {}).get(tipo, 0)
        tenta_global = tentativa_global if tentativa_global is not None else attempt
        limite_tipo_ok = tenta_tipo < max_tipo
        limite_global_ok = tenta_global < max_global
        deve_retry_base = limite_tipo_ok and limite_global_ok
        logger.debug(
            "[erro] limites nif=%s tipo=%s tenta_tipo=%d/%d tenta_global=%d/%d -> tipo_ok=%s global_ok=%s",
            nif, tipo, tenta_tipo, max_tipo, tenta_global, max_global, limite_tipo_ok, limite_global_ok,
        )
    else:
        # legado: attempt / retry_count
        max_tipo = retry_count
        max_global = retry_count
        tenta_tipo = attempt
        tenta_global = attempt
        deve_retry_base = attempt < retry_count

    # --- Decisão por tipo ---
    if tipo == TIPO_RATE_LIMIT_MINUTE:
        espera = get_tempo_espera(tipo)
        if modo_novo:
            max_tipo = get_max_tentativas(tipo)
            max_global = get_max_tentativas_global()
            tenta_tipo = (tentativas_por_tipo or {}).get(tipo, 0)
            tenta_global = tentativa_global if tentativa_global is not None else attempt
            limite_tipo_ok = tenta_tipo < max_tipo
            limite_global_ok = tenta_global < max_global
            if not limite_global_ok:
                deve_retry = False
                motivo = f"limite global {tenta_global}/{max_global}"
            elif not limite_tipo_ok:
                deve_retry = False
                motivo = f"limite tipo {tenta_tipo}/{max_tipo}"
            else:
                deve_retry = True
                motivo = "ok"
        else:
            deve_retry = attempt < retry_count
            motivo = "legado"
            max_tipo = retry_count
            max_global = retry_count
            tenta_tipo = attempt
            tenta_global = attempt
        acao = "retry" if deve_retry else "abort_retry_esgotado"
        guardar_erro(nif, tipo, codigo, mensagem, left, data, acao=f"retry_{espera}s" if deve_retry else "abort_retry_esgotado", run_id=run_id)
        if deve_retry:
            logger.warning(
                "[rate-limit] Limite por minuto nif=%s left_minute=%s — espera %ss retry tipo %d/%d global %d/%d (%s)",
                nif,
                left.get("minute") if isinstance(left, dict) else "?",
                espera,
                tenta_tipo + 1,
                max_tipo,
                tenta_global + 1,
                max_global,
                motivo,
            )
        else:
            logger.error(
                "[rate-limit] Limite por minuto — retries esgotados nif=%s tipo %d/%d global %d/%d motivo=%s",
                nif, tenta_tipo, max_tipo, tenta_global, max_global, motivo,
            )
        logger.debug("[erro] tratar_erro(%s) -> %s (%.2fs)", nif, tipo, time.perf_counter() - t)
        return {
            "tipo": tipo,
            "acao": "retry" if deve_retry else "abort",
            "espera": espera if deve_retry else 0,
            "deve_retry": deve_retry,
            "mensagem": mensagem,
            "codigo": codigo,
            "max_tipo": max_tipo,
            "max_global": max_global,
            "tentativas_tipo": tenta_tipo,
            "tentativa_global": tenta_global,
        }

    if tipo == TIPO_RATE_LIMIT_HOUR:
        espera = get_tempo_espera(tipo)
        if modo_novo:
            max_tipo = get_max_tentativas(tipo)
            max_global = get_max_tentativas_global()
            tenta_tipo = (tentativas_por_tipo or {}).get(tipo, 0)
            tenta_global = tentativa_global if tentativa_global is not None else attempt
            limite_tipo_ok = tenta_tipo < max_tipo
            limite_global_ok = tenta_global < max_global
            if not limite_global_ok:
                deve_retry = False
                motivo = f"limite global {tenta_global}/{max_global}"
            elif not limite_tipo_ok:
                deve_retry = False
                motivo = f"limite tipo {tenta_tipo}/{max_tipo}"
            else:
                deve_retry = True
                motivo = "ok"
        else:
            deve_retry = attempt < retry_count
            motivo = "legado"
            max_tipo = retry_count
            max_global = retry_count
            tenta_tipo = attempt
            tenta_global = attempt
        acao = "retry" if deve_retry else "abort_retry_esgotado"
        guardar_erro(nif, tipo, codigo, mensagem, left, data, acao=f"retry_{espera}s" if deve_retry else "abort_retry_esgotado", run_id=run_id)
        if deve_retry:
            logger.warning(
                "[rate-limit] Limite por hora nif=%s left_hour=%s — espera %ss (%dh) retry tipo %d/%d global %d/%d (%s)",
                nif,
                left.get("hour") if isinstance(left, dict) else "?",
                espera,
                espera // 3600,
                tenta_tipo + 1,
                max_tipo,
                tenta_global + 1,
                max_global,
                motivo,
            )
        else:
            logger.error("[rate-limit] Limite por hora — retries esgotados nif=%s tipo %d/%d global %d/%d motivo=%s", nif, tenta_tipo, max_tipo, tenta_global, max_global, motivo)
        logger.debug("[erro] tratar_erro(%s) -> %s (%.2fs)", nif, tipo, time.perf_counter() - t)
        return {
            "tipo": tipo,
            "acao": "retry" if deve_retry else "abort",
            "espera": espera if deve_retry else 0,
            "deve_retry": deve_retry,
            "mensagem": mensagem,
            "codigo": codigo,
            "max_tipo": max_tipo,
            "max_global": max_global,
            "tentativas_tipo": tenta_tipo,
            "tentativa_global": tenta_global,
        }

    if tipo == TIPO_RATE_LIMIT_DAY:
        max_tipo = get_max_tentativas(tipo)
        max_global = get_max_tentativas_global()
        tenta_tipo = (tentativas_por_tipo or {}).get(tipo, 0) if modo_novo else attempt
        tenta_global = tentativa_global if tentativa_global is not None else attempt
        # dia/mês são fatais; mesmo que max_tipo >0, aborta (config 0 por defeito)
        guardar_erro(nif, tipo, codigo, mensagem, left, data, acao="abort_day", run_id=run_id)
        logger.error(
            "[rate-limit] Limite por dia atingido nif=%s left_day=%s tipo %d/%d global %d/%d — a encerrar app",
            nif, left.get("day") if isinstance(left, dict) else "?", tenta_tipo, max_tipo, tenta_global, max_global,
        )
        logger.info("-" * 49)
        logger.info("| Erro fatal - quota diária excedida               |")
        logger.info("| NIF         : %-30s |", str(nif))
        logger.info("| Tipo        : %-30s |", tipo)
        logger.info("| Mensagem    : %-30s |", mensagem[:30])
        logger.info("-" * 49)
        logger.debug("[erro] tratar_erro(%s) -> %s ABORT (%.2fs)", nif, tipo, time.perf_counter() - t)
        return {"tipo": tipo, "acao": "abort", "espera": 0, "deve_retry": False, "mensagem": mensagem, "codigo": codigo, "max_tipo": max_tipo, "max_global": max_global, "tentativas_tipo": tenta_tipo, "tentativa_global": tenta_global}

    if tipo == TIPO_RATE_LIMIT_MONTH:
        max_tipo = get_max_tentativas(tipo)
        max_global = get_max_tentativas_global()
        tenta_tipo = (tentativas_por_tipo or {}).get(tipo, 0) if modo_novo else attempt
        tenta_global = tentativa_global if tentativa_global is not None else attempt
        guardar_erro(nif, tipo, codigo, mensagem, left, data, acao="abort_month", run_id=run_id)
        logger.error(
            "[rate-limit] Limite por mês atingido nif=%s left_month=%s tipo %d/%d global %d/%d — a encerrar app",
            nif, left.get("month") if isinstance(left, dict) else "?", tenta_tipo, max_tipo, tenta_global, max_global,
        )
        logger.info("-" * 49)
        logger.info("| Erro fatal - quota mensal excedida               |")
        logger.info("| NIF         : %-30s |", str(nif))
        logger.info("| Tipo        : %-30s |", tipo)
        logger.info("| Mensagem    : %-30s |", mensagem[:30])
        logger.info("-" * 49)
        logger.debug("[erro] tratar_erro(%s) -> %s ABORT (%.2fs)", nif, tipo, time.perf_counter() - t)
        return {"tipo": tipo, "acao": "abort", "espera": 0, "deve_retry": False, "mensagem": mensagem, "codigo": codigo, "max_tipo": max_tipo, "max_global": max_global, "tentativas_tipo": tenta_tipo, "tentativa_global": tenta_global}

    if tipo == TIPO_RATE_LIMIT_PAID:
        max_tipo = get_max_tentativas(tipo)
        max_global = get_max_tentativas_global()
        tenta_tipo = (tentativas_por_tipo or {}).get(tipo, 0) if modo_novo else attempt
        tenta_global = tentativa_global if tentativa_global is not None else attempt
        guardar_erro(nif, tipo, codigo, mensagem, left, data, acao="abort_paid", run_id=run_id)
        logger.error("[rate-limit] Créditos pagos esgotados nif=%s tipo %d/%d global %d/%d", nif, tenta_tipo, max_tipo, tenta_global, max_global)
        logger.debug("[erro] tratar_erro(%s) -> %s ABORT (%.2fs)", nif, tipo, time.perf_counter() - t)
        return {"tipo": tipo, "acao": "abort", "espera": 0, "deve_retry": False, "mensagem": mensagem, "codigo": codigo, "max_tipo": max_tipo, "max_global": max_global, "tentativas_tipo": tenta_tipo, "tentativa_global": tenta_global}

    # Genérico / unknown — guardar e devolver sem retry automático
    # (o chamador decide; por defeito não retry)
    if tipo in (TIPO_GENERIC_ERROR, TIPO_UNKNOWN):
        # Para erros genéricos da API (ex: NIF não encontrado), guardar como info mas não abortar por quota
        # Só persistimos para auditoria
        max_tipo = get_max_tentativas(tipo)
        max_global = get_max_tentativas_global()
        tenta_tipo = (tentativas_por_tipo or {}).get(tipo, 0) if modo_novo else attempt
        tenta_global = tentativa_global if tentativa_global is not None else attempt
        guardar_erro(nif, tipo, codigo, mensagem, left if isinstance(left, dict) else {}, data, acao="none", run_id=run_id)
        logger.warning("[erro] Erro genérico API nif=%s tipo=%s msg='%.120s' tipo %d/%d global %d/%d", nif, tipo, mensagem, tenta_tipo, max_tipo, tenta_global, max_global)
        logger.debug("[erro] tratar_erro(%s) -> %s (%.2fs)", nif, tipo, time.perf_counter() - t)
        return {"tipo": tipo, "acao": "none", "espera": 0, "deve_retry": False, "mensagem": mensagem, "codigo": codigo, "max_tipo": max_tipo, "max_global": max_global, "tentativas_tipo": tenta_tipo, "tentativa_global": tenta_global}

    # fallback
    guardar_erro(nif, tipo, codigo, mensagem, left if isinstance(left, dict) else {}, data, acao="none", run_id=run_id)
    return {"tipo": tipo, "acao": "none", "espera": 0, "deve_retry": False, "mensagem": mensagem, "codigo": codigo, "max_tipo": 0, "max_global": get_max_tentativas_global(), "tentativas_tipo": 0, "tentativa_global": tentativa_global if tentativa_global is not None else attempt}


# Alias para compatibilidade com enunciado: "recebe a mensagem de erro e a trata"
def handle_error(nif: str, data: dict, attempt: int = 0, retry_count: int = 1, tentativas_por_tipo: dict | None = None, tentativa_global: int | None = None, run_id: str | None = None) -> dict:
    """Alias de :func:`tratar_erro` (compatibilidade enunciado).

    Args:
        nif: Ver :func:`tratar_erro`.
        data: Ver :func:`tratar_erro`.
        attempt: Ver :func:`tratar_erro`.
        retry_count: Ver :func:`tratar_erro`.
        tentativas_por_tipo: Ver :func:`tratar_erro`.
        tentativa_global: Ver :func:`tratar_erro`.

    Returns:
        Mesmo dict de :func:`tratar_erro`.

    Examples:
        >>> handle_error("509442013", {"result": "error", "message": "Limit per minute"})  # doctest: +SKIP
        {'tipo': 'rate_limit_minute', 'acao': 'retry', ...}
    """
    return tratar_erro(nif, data, attempt, retry_count, tentativas_por_tipo, tentativa_global, run_id)


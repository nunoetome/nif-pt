#!/usr/bin/env python3
"""
importar_nif — Normaliza JSON do consulta_nif.py e insere em Azure SQL staging.

Lê JSON de ``stdin`` (pipeline), valida, mapeia 36 colunas via
:func:`mapear_registo` e insere em ``{sql_schema}.{tabela_staging}``
(``stg_nunotome.nif_pt_stg`` por defeito) via ``pyodbc`` + ``ODBC Driver 18``.

Uso:
    python consulta_nif.py 509442013 | python importar_nif.py
    python importar_nif.py < ficheiro.json
    python consulta_nif.py 509442013 > tmp.json && python importar_nif.py < tmp.json

    Insere sempre em ``nif_pt_stg``. A promoção para ``nif_pt`` é feita
    por ``MERGE`` / procedure noutro processo.

Configuração (``config/config.py:get_config("importar_nif")``):
    * ``sql_server`` — ``kiwa-pt-operations.database.windows.net``
    * ``sql_database`` — ``kiwa-pt-operations``
    * ``sql_schema`` — ``stg_nunotome``
    * ``sql_driver`` — ``ODBC Driver 18 for SQL Server``
    * ``tabela_staging`` — ``nif_pt_stg``
    * ``AZURE_USER`` / ``AZURE_PALAVRA_CHAVE`` — ``config/.env``

Exemplos:
    >>> from importar_nif import mapear_registo
    >>> r = {"nif": "509442013", "fonte": "nif.pt", "nif_valido_formato": True,
    ...      "dados": {"title": "X", "place": {"city": "Porto"}, "contacts": {}},
    ...      "creditos": {"used": "free", "left": []}}
    >>> m = mapear_registo(r)
    >>> m["nif"], m["place_city"]
    (509442013, 'Porto')

See Also:
    :mod:`consulta_nif`, :mod:`importar_nif_sqlite`, :mod:`utils.error_handler`
"""

import json
import logging
import sys
import time
from datetime import date, datetime

from config.config import get_config
from Logging.logging_orchestrator import setup_logging
from utils.run_id import ensure_run_id, extract_cli_run_id, get_run_id, set_run_id
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
    """Constrói a *connection string* ODBC para Azure SQL.

    Usa ``SQL_DRIVER`` / ``SQL_SERVER`` / ``SQL_DATABASE`` / ``AZURE_USER`` /
    ``AZURE_PALAVRA_CHAVE`` de ``config.yaml`` + ``.env``, com
    ``Encrypt=yes;TrustServerCertificate=no;`` (exigido pelo Azure).

    Returns:
        String ``DRIVER={...};SERVER=...;DATABASE=...;UID=...;PWD=...;Encrypt=yes;...``.
        A password **não** é logada; user é mascarado no :func:`main`.

    Examples:
        >>> cs = connection_string()  # doctest: +SKIP
        >>> "ODBC Driver 18" in cs
        True

    Notas:
        * TIMING ``%.2fs`` (R9) + TAG ``[db]``.
        * ``TrustServerCertificate=no`` — falhar se certificado inválido.
    """
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
    """Extrai CAE(s) do registo nif.pt como CSV.

    A API devolve ``cae`` como ``list`` (ex. ``["62010","63120"]``) ou
    ``str``. A função normaliza para string única com vírgulas.

    Args:
        registo: ``resultado["dados"]`` (dict com chave ``cae``).

    Returns:
        ``"62010,63120"`` se lista, ``str(cae)`` se string, ``None`` se
        ausente/``None``.

    Examples:
        >>> extrair_cae({"cae": ["62010", "63120"]})
        '62010,63120'
        >>> extrair_cae({"cae": "62010"})
        '62010'
        >>> extrair_cae({}) is None
        True
    """
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
    """Converte valor de data da API para ``datetime.date``.

    Aceita ``YYYY-MM-DD`` (ISO) com ou sem ``Z`` e já-``date``. Falhas
    devolvem ``None`` sem levantar.

    Args:
        val: Valor de ``dados.start_date`` (str, date ou falsy).

    Returns:
        ``date`` ou ``None`` se vazio / inválido.

    Examples:
        >>> parse_date("2010-05-18")
        datetime.date(2010, 5, 18)
        >>> parse_date("2010-05-18Z")
        datetime.date(2010, 5, 18)
        >>> parse_date("") is None
        True
        >>> parse_date(None) is None
        True
    """
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
    """Converte capital social da API para ``float``.

    A API devolve ``"248000.00"`` ou ``"248.000,00"`` (PT). A função troca
    vírgula por ponto antes de ``float()``.

    Args:
        val: ``dados.structure.capital`` (str/float/None).

    Returns:
        ``float`` ou ``None`` se vazio / inválido.

    Examples:
        >>> parse_capital("248000.00")
        248000.0
        >>> parse_capital("248,50")
        248.5
        >>> parse_capital(None) is None
        True
    """
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
    """Converte valor para ``int`` de forma segura.

    Usado para ``creditos.left.*``. ``None`` ou falha → ``None``.

    Args:
        val: Valor a converter.

    Returns:
        ``int`` ou ``None``.

    Examples:
        >>> parse_int("5")
        5
        >>> parse_int(None) is None
        True
        >>> parse_int("abc") is None
        True
    """
    if val is None:
        return None
    try:
        result = int(val)
        return result
    except (ValueError, TypeError) as e:
        logger.debug("[map] parse_int falha '%s': %s", val, e)
        return None


def mapear_registo(resultado: dict, run_id: str | None = None) -> dict:
    """Mapeia o JSON normalizado de :func:`consulta_nif.consultar_nif` para 37 colunas SQL.

    Desembrulha ``resultado["dados"]`` (``place``, ``geo``, ``contacts``,
    ``structure``, ``cae``) + ``resultado["creditos"]`` e aplica
    :func:`parse_date` / :func:`parse_capital` / :func:`parse_int` /
    :func:`extrair_cae`. Trata o caso ``credits.left == []`` (free plan →
    ``{}``). Inclui ``run_id`` para rastreabilidade por execução.

    Args:
        resultado: Dict devolvido por :func:`consulta_nif.consultar_nif`
            (``nif``, ``fonte``, ``dados``, ``creditos``, ``nif_valido_formato``).
        run_id: Identificador da execução. Se ``None`` tenta
            ``resultado["run_id"]`` ou ``utils.run_id.get_run_id()``.

    Returns:
        Dict com 37 chaves — ordem de :func:`colunas_tabela`:

        * ``nif`` (int), ``nif_valido_formato`` (0/1), ``consulta_origem``,
        * ``seo_url``, ``title``, ``alias``, ``status``, ``start_date`` (date|None),
          ``activity``,
        * ``place_address/pc4/pc3/city``, ``address/pc4/pc3/city``,
        * ``geo_region/county/parish``,
        * ``contacts_email/phone/website/fax``,
        * ``structure_nature/capital/capital_currency``,
        * ``cae`` (CSV), ``racius``, ``portugalio``,
        * ``creditos_used``, ``creditos_left_month/day/hour/minute/paid`` (int|None),
        * ``run_id`` (str|None) — identificador da execução.

    Examples:
        >>> r = {"nif": "509442013", "fonte": "nif.pt", "nif_valido_formato": True,
        ...      "dados": {"title": "X", "cae": ["62010"], "place": {"city": "Porto"},
        ...                "contacts": {"email": "a@b.pt"}, "structure": {"capital": "1000"}},
        ...      "creditos": {"used": "free", "left": []}}
        >>> mapear_registo(r)["cae"]
        '62010'
        >>> mapear_registo(r)["creditos_left_month"] is None
        True

    See Also:
        :func:`colunas_tabela`, :func:`valores_para_insert`, :func:`extrair_cae`
    """
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
    # run_id — CLI > payload > contexto
    _run_id = run_id or resultado.get("run_id") or get_run_id()

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
        "run_id": _run_id,
    }

    logger.info(
        "[map] 37 cols mapeadas nif=%s title=%.30s cae=%s credits used=%s left_month=%s run_id=%s",
        mapped.get("nif"),
        (mapped.get("title") or "")[:30],
        (mapped.get("cae") or "")[:50],
        mapped.get("creditos_used"),
        mapped.get("creditos_left_month"),
        (_run_id[:8] + "...") if _run_id else "—",
    )
    logger.debug("[map] mapear_registo() -> %.2fs", time.perf_counter() - t)
    return mapped


def colunas_tabela() -> list[str]:
    """Devolve a lista ordenada das 37 colunas para ``INSERT`` em ``nif_pt_stg``.

    Exclui colunas com ``DEFAULT`` (``id``, ``data_consulta``,
    ``data_staging``, ``processado``) — o ``INSERT`` omite-as intencionalmente.

    Returns:
        Lista de 37 nomes — 1 ``nif`` + 36 restantes na ordem do DDL
        ``sql/01_criar_tabelas.sql`` (inclui ``run_id``).

    Examples:
        >>> len(colunas_tabela())
        37
        >>> colunas_tabela()[:3]
        ['nif', 'nif_valido_formato', 'consulta_origem']
    """
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
        "run_id",
    ]


def placeholders() -> str:
    """Gera placeholders ``?`` para ``pyodbc`` na ordem de :func:`colunas_tabela`.

    Returns:
        String ``"?,?,?,?,..."`` com 36 ``?`` separados por vírgula.

    Examples:
        >>> placeholders().count("?")
        36
    """
    return ",".join("?" for _ in colunas_tabela())


def valores_para_insert(reg: dict) -> list:
    """Extrai valores do dict mapeado na ordem de :func:`colunas_tabela`.

    Args:
        reg: Dict devolvido por :func:`mapear_registo`.

    Returns:
        Lista de 36 valores na ordem das colunas — pronta para
        ``cursor.execute(sql, valores_para_insert(reg))``.

    Examples:
        >>> reg = {"nif": 509442013, "title": "X"}
        >>> valores_para_insert(reg)[0]
        509442013
    """
    cols = colunas_tabela()
    return [reg.get(c) for c in cols]


def main():
    """Ponto de entrada CLI — lê JSON de stdin, mapeia e insere em Azure SQL.

    Fluxo:

    1. ``setup_logging()`` + BANNER ``= 49`` + ``run_id``.
    2. ``sys.stdin.read()`` — ``exit 1`` se vazio.
    3. ``json.loads`` — ``exit 1`` se inválido.
    4. Se ``resultado["erro"]`` → log + ``exit 1`` (não insere).
    5. ``mapear_registo(resultado)`` → 37 cols (inclui ``run_id``).
    6. Valida ``AZURE_USER`` / ``AZURE_PALAVRA_CHAVE`` — ``exit 1`` se falta.
    7. ``pyodbc.connect(connection_string(), timeout=30)`` com ``autocommit=False``.
    8. ``INSERT INTO {TABELA_STAGING} (37 cols) VALUES (37 ?)`` + ``commit``
       (``rollback`` em ``pyodbc.Error``) + BOX ``Inserido em Azure SQL``.
       Fallback sem ``run_id`` se coluna falta (BD antiga).

    Args:
        Nenhum — lê ``sys.stdin`` integralmente. Aceita ``--run-id <uuid>``.

    Returns:
        Não retorna — ``sys.exit(0)`` em sucesso, ``sys.exit(1)`` em erro.
        ``stderr`` com TAGs ``[io][map][db][run]``; ``stdout`` vazio.

    See Also:
        :func:`mapear_registo`, :func:`connection_string`, :func:`colunas_tabela`
    """
    logger_main = setup_logging()
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt importar_nif a iniciar ':=^49}")
    logger_main.info("=" * 49)
    t_app = time.perf_counter()

    cli_run_id = extract_cli_run_id()
    if cli_run_id:
        set_run_id(cli_run_id)
        logger_main.info("[run] run_id (cli)=%s", cli_run_id)

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
        logger_main.debug("[io] JSON carregado nif=%s run_id=%s", resultado.get("nif"), resultado.get("run_id"))
    except json.JSONDecodeError as e:
        logger_main.error("[io] JSON inválido: %s (preview=%.80s)", e, raw[:80])
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    _run_id = ensure_run_id(cli_value=cli_run_id, payload_value=resultado.get("run_id"))
    if not resultado.get("run_id"):
        logger_main.warning("[run] run_id ausente no JSON — gerado novo %s", _run_id[:8])
        resultado["run_id"] = _run_id
    else:
        logger_main.info("[run] run_id=%s (herdado do JSON)", _run_id)

    if resultado.get("erro"):
        logger_main.warning("[api] Erro consulta propagado: %s run_id=%s", resultado["erro"], _run_id[:8])
        # mostrar também message detalhada se existir em dados
        dados = resultado.get("dados") or {}
        if isinstance(dados, dict) and dados.get("message"):
            logger_main.warning("[api] Detalhe: %s", dados.get("message"))
        logger_main.info("[run] run_id=%s", _run_id)
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
    reg = mapear_registo(resultado, run_id=_run_id)

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
        try:
            cursor.execute(sql_insert_stg, vals)
        except pyodbc.Error as ie:
            # fallback se coluna run_id falta na BD antiga
            if "run_id" in str(ie).lower():
                logger_main.warning("[db] Coluna run_id em falta — fallback sem run_id: %s", ie)
                cols_fb = [c for c in cols if c != "run_id"]
                vals_fb = [reg.get(c) for c in cols_fb]
                sql_fb = f"INSERT INTO {TABELA_STAGING} ({','.join(cols_fb)}) VALUES ({','.join('?' for _ in cols_fb)})"
                cursor.execute(sql_fb, vals_fb)
            else:
                raise
        logger_main.info("[db] INSERT %s nif=%s run_id=%s -> 1 row em %.2fs", TABELA_STAGING, nif, _run_id[:8], time.perf_counter() - t_insert)
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
        logger_main.info("| run_id      : %-30s |", _run_id[:30])
        logger_main.info("| Tempo       : %-30s |", f"{time.perf_counter() - t_app:.2f}s")
        logger_main.info("-" * 49)
    except pyodbc.Error as e:
        conn.rollback()
        logger_main.error("[db] Falha inserção nif=%s run_id=%s: %s", nif, _run_id[:8], e)
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

    logger_main.info("[run] run_id=%s", _run_id)
    logger_main.info("Importar concluído em %.2fs", time.perf_counter() - t_app)
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt importar_nif finalizado ':=^49}")
    logger_main.info("=" * 49)


if __name__ == "__main__":
    main()

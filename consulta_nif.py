#!/usr/bin/env python3
"""
consulta_nif — Consulta de NIF português via API nif.pt.

Módulo principal de recolha. Valida o NIF com o algoritmo Mod-11 da AT,
consulta ``http://www.nif.pt/?json=1&q=<NIF>&key=<KEY>`` via ``requests``,
e devolve um dicionário normalizado sempre com as chaves
``nif / valido / fonte / erro / dados / nif_valido_formato / creditos``.

Pipeline Unix
-------------
O módulo escreve **apenas JSON** em ``stdout`` (``json.dumps``) e todas
as mensagens humanas vão para ``stderr`` via :mod:`Logging.logging_orchestrator`,
permitindo ``| python importar_nif_sqlite.py`` sem quebrar o pipe.

Exemplos
--------
>>> from consulta_nif import validar_nif
>>> validar_nif("509442013")
True
>>> validar_nif("123456789")
False
>>> validar_nif("999999990")  # dígito de controlo inválido
False

CLI:
    $ python consulta_nif.py 509442013
    $ python consulta_nif.py 509442013 | python importar_nif_sqlite.py

Configuração
------------
Lida via :func:`config.config.get_config` (``config/config.yaml`` +
``config/.env``):

* ``api_base`` — base URL (default ``http://www.nif.pt``)
* ``NIF_PT_KEY`` / ``NIF-PT-KEY`` — chave da API (``.env`` com hífen)
* ``timeout`` — segundos para ``requests.get`` (default ``10``)
* ``retry_count`` / ``max_tentativas_*`` — limites de retry (ver :mod:`utils.error_handler`)
* ``tempo_de_espera`` / ``tempo_espera_minuto`` / ``hora`` — esperas por janela rate-limit

Logging
-------
Usa :func:`Logging.logging_orchestrator.setup_logging` com prefixo
``<<nif-pt>>``, ``RotatingFileHandler`` (10 MB / 5000 recs / 10 backups),
ficheiro ``log_files/nif_pt.log`` e estilos R1–R9 (BANNER ``= 49``, BOX, TAG
``[api][valid][cfg]``, TIMING ``%.2fs`` com ``time.perf_counter``).

Notas
-----
* ``NIF-PT-KEY`` com hífen é intencional — ``os.getenv("NIF-PT-KEY")``.
* O campo ``tipo_erro`` só aparece em respostas de erro classificadas
  por :func:`utils.error_handler.tratar_erro`.
"""

import json
import logging
import sys
import time
from pathlib import Path

import requests
from config.config import get_config
from Logging.logging_orchestrator import setup_logging
from utils.run_id import (
    ensure_run_id,
    extract_cli_run_id,
    generate_run_id,
    get_run_id,
    remove_run_id_args,
    set_run_id,
)

logger = logging.getLogger(__name__)

cfg = get_config("consulta_nif")

API_BASE = cfg.get("api_base", "http://www.nif.pt")
API_KEY = cfg.get("NIF_PT_KEY")
TIMEOUT = cfg.get("timeout", 10)
RETRY_COUNT = cfg.get("retry_count", 1)
TEMPO_ESPERA = cfg.get("tempo_de_espera", 60)
# Tempos específicos por janela rate-limit (nova camada erro)
TEMPO_ESPERA_MINUTO = cfg.get("tempo_espera_minuto", 60)
TEMPO_ESPERA_HORA = cfg.get("tempo_espera_hora", 3600)
# Limites de tentativas — por tipo e global
MAX_TENTATIVAS_GLOBAL = cfg.get("max_tentativas_global", cfg.get("retry_count", 1))
MAX_TENTATIVAS_MINUTO = cfg.get("max_tentativas_minuto", 3)
MAX_TENTATIVAS_HORA = cfg.get("max_tentativas_hora", 2)
MAX_TENTATIVAS_DIA = cfg.get("max_tentativas_dia", 0)
MAX_TENTATIVAS_MES = cfg.get("max_tentativas_mes", 0)

# Aviso se timeout excessivo
if TIMEOUT and TIMEOUT > 60:
    # logger ainda pode não ter handlers nesta fase (antes de setup_logging)
    # mas a mensagem será capturada após setup no main
    pass


def validar_nif(nif: str) -> bool:
    """Valida o NIF português pelo algoritmo Mod-11 da Autoridade Tributária.

    Implementa a fórmula oficial da AT: para os 8 primeiros dígitos
    ``d[0..7]`` calcula ``total = Σ d[i] * (9-i)``, ``resto = total % 11``,
    ``digito = 0`` se ``resto in (0,1)`` senão ``11 - resto``. O NIF é válido
    quando ``digito == d[8]`` (9.º dígito).

    A função **não** consulta a API nem consome créditos; serve de filtro
    local antes de :func:`consultar_nif`.

    Args:
        nif: String com 9 caracteres. Deve conter apenas dígitos ``0-9``;
            espaços, hífens ou prefixo ``PT`` invalidam.

    Returns:
        ``True`` se o NIF tem 9 dígitos, não é ``000000000`` e o dígito de
        controlo bate certo; ``False`` caso contrário.

    Examples:
        >>> validar_nif("509442013")
        True
        >>> validar_nif("501442013")  # exemplo genérico
        False
        >>> validar_nif("123")
        False
        >>> validar_nif("PT509442013")
        False

    See Also:
        :func:`consultar_nif` — usa este validador para preencher o campo
        ``valido`` / ``nif_valido_formato`` do JSON de saída.

    Notas:
        * ``000000000`` é rejeitado explicitamente (``nif_int == 0``).
        * O logging usa TAG ``[valid]`` e TIMING ``%.2fs`` (R9).
    """
    logger.debug(f"{' validar_nif() ':~^49}")
    t = time.perf_counter()
    if not nif.isdigit() or len(nif) != 9:
        logger.warning("[valid] NIF '%s' formato inválido (len=%d isdigit=%s)", nif, len(nif), nif.isdigit() if nif else False)
        logger.debug("[valid] validar_nif(%s) -> FAIL (%.2fs)", nif, time.perf_counter() - t)
        return False
    nif_int = int(nif)
    if nif_int == 0:
        logger.warning("[valid] NIF '%s' é zero", nif)
        logger.debug("[valid] validar_nif(%s) -> FAIL (%.2fs)", nif, time.perf_counter() - t)
        return False
    total = sum(int(d) * (9 - i) for i, d in enumerate(nif[:8]))
    resto = total % 11
    digito_controlo = 0 if resto in (0, 1) else 11 - resto
    ok = digito_controlo == int(nif[8])
    logger.debug(
        "[valid] NIF %s Mod-11 %s (total=%d resto=%d digito=%d esperado=%s)",
        nif,
        "OK" if ok else "FAIL",
        total,
        resto,
        digito_controlo,
        nif[8],
    )
    if not ok:
        logger.warning(
            "[valid] NIF %s dígito de controlo inválido (calculado=%d, recebido=%s)",
            nif,
            digito_controlo,
            nif[8],
        )
    logger.debug("[valid] validar_nif(%s) -> %s (%.2fs)", nif, ok, time.perf_counter() - t)
    return ok


def consultar_nif(nif: str, run_id: str | None = None) -> dict:
    """Consulta a API ``nif.pt`` para o NIF dado e devolve dict normalizado.

    Faz ``GET {API_BASE}/?json=1&q=<nif>&key=<NIF_PT_KEY>`` com
    ``timeout=TIMEOUT`` e ``requests.get``. Em caso de ``result != "success"``
    delega a classificação / persistência / decisão de retry a
    :func:`utils.error_handler.tratar_erro` (rate-limit minuto/hora → retry
    ``60s/3600s``, dia/mês/paid → abort, genérico → ``none``).

    A função gere um *loop* global ``for tentativa_global in range(max_global+1)``
    e um dicionário ``tentativas_por_tipo`` para respeitar os limites
    ``max_tentativas_global`` / ``minuto`` / ``hora`` / ``dia`` / ``mes``
    definidos em ``config/config.yaml``.

    Args:
        nif: NIF com 9 dígitos (já validado opcionalmente por
            :func:`validar_nif`). Não precisa ser válido — a API é sempre
            consultada se ``NIF-PT-KEY`` existir.
        run_id: Identificador da execução (UUID v4). Se ``None`` tenta
            resolver via :func:`utils.run_id.get_run_id` ou gera novo.

    Returns:
        Dicionário com chaves estáveis (sempre presentes):

        * ``nif`` (``str``) — NIF consultado.
        * ``valido`` (``bool``) — resultado de :func:`validar_nif`.
        * ``fonte`` (``str | None``) — ``"nif.pt"`` ou ``None`` se sem chave.
        * ``erro`` (``str | None``) — ``None`` em sucesso, mensagem caso contrário.
        * ``dados`` (``dict | None``) — ``records[nif]`` em sucesso, payload
          completo da API em erro, ``None`` em erro de rede/timeout.
        * ``nif_valido_formato`` (``bool | None``) — ``data["nif_validation"]``.
        * ``creditos`` (``dict | None``) — ``data["credits"]`` (``{"used","left"}``).
        * ``tipo_erro`` (``str``) — só em erro classificado (ex.
          ``"rate_limit_minute"``).
        * ``run_id`` (``str``) — identificador da execução (sempre presente).

        Em sucesso ``erro is None`` e ``valido is True``; em erro
        ``erro`` contém ``message`` ou ``result`` da API.

    Raises:
        Não levanta exceções para o chamador — todos os
        ``requests.exceptions.Timeout``, ``RequestException`` e
        ``json.JSONDecodeError`` são capturados e convertidos em dict de erro.
        Falhas no :mod:`utils.error_handler` fazem fallback para lógica
        antiga sem quebrar o fluxo.

    Examples:
        >>> r = consultar_nif("509442013")  # doctest: +SKIP
        >>> r["erro"] is None and r["valido"] is True
        True
        >>> r["dados"]["title"]  # doctest: +SKIP
        'Nexperience, Unipessoal, Lda'
        >>> consultar_nif("000000000")["erro"] is not None  # doctest: +SKIP
        True

    See Also:
        :func:`validar_nif`, :func:`utils.error_handler.classificar_erro`,
        :func:`utils.error_handler.tratar_erro`, :func:`utils.error_handler.guardar_erro`.

    Notas:
        * ``API_KEY`` mascarada no log como ``***XXXX``.
        * ``records`` é ``dict`` com NIF como chave; usa fallback
          ``records[list(records)[0]]`` quando a chave exata não existe.
        * ``credits.left`` pode ser ``[]`` (free plan) em vez de ``dict``.
        * Logging: TAG ``[api]`` + TIMING (R9) + BOX de resumo no :func:`main`.
    """
    # run_id — resolve contexto ou gera novo para esta chamada
    _run_id = run_id or get_run_id() or generate_run_id()
    if run_id:
        set_run_id(_run_id)
    elif not get_run_id():
        set_run_id(_run_id)

    logger.debug(f"{' consultar_nif() ':~^49}")
    t_total = time.perf_counter()
    logger.debug("[run] run_id=%s nif=%s", _run_id, nif)

    if not API_KEY:
        logger.error("[cfg] NIF-PT-KEY não encontrada no config/.env run_id=%s", _run_id[:8])
        return {
            "nif": nif,
            "valido": validar_nif(nif),
            "fonte": None,
            "erro": "NIF-PT-KEY não encontrada no .env",
            "dados": None,
            "run_id": _run_id,
        }

    url = f"{API_BASE}/"
    params = {"json": 1, "q": nif, "key": API_KEY}
    masked_key = f"***{API_KEY[-4:]}" if API_KEY and len(API_KEY) >= 4 else "***"
    logger.info("[api] GET %s?q=%s key=%s timeout=%ss", API_BASE, nif, masked_key, TIMEOUT)

    last_error = None
    # Tracking — limites por tipo + global
    tentativas_por_tipo: dict = {}
    # Usa MAX global como limite do loop (fallback para retry_count legado)
    max_global_loop = MAX_TENTATIVAS_GLOBAL
    logger.debug("[api] Limites global=%d minuto=%d hora=%d dia=%d mes=%d", MAX_TENTATIVAS_GLOBAL, MAX_TENTATIVAS_MINUTO, MAX_TENTATIVAS_HORA, MAX_TENTATIVAS_DIA, MAX_TENTATIVAS_MES)
    for tentativa_global in range(max_global_loop + 1):
        t_req = time.perf_counter()
        try:
            logger.debug("[api] Tentativa %d/%d GET %s params q=%s", tentativa_global + 1, max_global_loop + 1, url, nif)
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "[api] GET nif.pt?q=%s -> %d %s em %.2fs",
                nif,
                resp.status_code,
                resp.reason,
                time.perf_counter() - t_req,
            )
        except requests.exceptions.Timeout:
            elapsed = time.perf_counter() - t_req
            logger.error("[api] Timeout na consulta nif.pt?q=%s após %.2fs (timeout=%s) tentativa %d/%d", nif, elapsed, TIMEOUT, tentativa_global + 1, max_global_loop + 1)
            last_error = {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt", "erro": "Timeout na consulta à API nif.pt", "dados": None, "run_id": _run_id}
            # Timeout conta para limite global
            if tentativa_global < max_global_loop:
                logger.warning("[api] Retry timeout em %ss (global %d/%d)", TEMPO_ESPERA, tentativa_global + 1, max_global_loop + 1)
                time.sleep(TEMPO_ESPERA)
                continue
            logger.debug("[api] consultar_nif(%s) -> FAIL Timeout global esgotado (%.2fs)", nif, time.perf_counter() - t_total)
            return last_error
        except requests.exceptions.RequestException as e:
            elapsed = time.perf_counter() - t_req
            logger.error("[api] Erro de rede nif.pt?q=%s: %s (%.2fs) tentativa %d/%d", nif, e, elapsed, tentativa_global + 1, max_global_loop + 1)
            last_error = {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt", "erro": f"Erro de rede: {e}", "dados": None, "run_id": _run_id}
            if tentativa_global < max_global_loop:
                logger.warning("[api] Retry rede em %ss (global %d/%d)", TEMPO_ESPERA, tentativa_global + 1, max_global_loop + 1)
                time.sleep(TEMPO_ESPERA)
                continue
            logger.debug("[api] consultar_nif(%s) -> FAIL rede global esgotado (%.2fs)", nif, time.perf_counter() - t_total)
            return last_error
        except json.JSONDecodeError:
            elapsed = time.perf_counter() - t_req
            body_len = len(resp.text) if 'resp' in locals() and hasattr(resp, 'text') else 0
            logger.error("[api] Resposta não JSON de nif.pt nif=%s body_len=%d (%.2fs)", nif, body_len, elapsed)
            return {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt", "erro": "Resposta inválida (não JSON) da API", "dados": None, "run_id": _run_id}

        # Sucesso HTTP mas result pode ser error -> delega à nova camada erro
        if data.get("result") != "success":
            result = data.get("result", "Erro desconhecido da API")
            message = data.get("message", "")
            erro_msg = message or result

            # --- Nova camada: utils.error_handler ---
            try:
                from utils.error_handler import tratar_erro
                decisao = tratar_erro(
                    nif,
                    data,
                    attempt=tentativa_global,
                    retry_count=RETRY_COUNT,
                    tentativas_por_tipo=tentativas_por_tipo,
                    tentativa_global=tentativa_global,
                    run_id=_run_id,
                )

                tipo = decisao.get("tipo", "unknown")
                acao = decisao.get("acao", "none")
                espera = decisao.get("espera", 0)
                deve_retry = decisao.get("deve_retry", False)

                # Actualiza contadores por tipo (para próxima iteração)
                tentativas_por_tipo[tipo] = tentativas_por_tipo.get(tipo, 0) + 1

                # Verifica limite global antes de retry
                if tentativa_global >= max_global_loop:
                    logger.error(
                        "[api] Limite global atingido nif=%s tipo=%s global %d/%d — abort",
                        nif, tipo, tentativa_global, max_global_loop,
                    )
                    logger.debug("[api] consultar_nif(%s) -> %s ABORT global (%.2fs)", nif, result, time.perf_counter() - t_total)
                    return {
                        "nif": nif,
                        "valido": validar_nif(nif),
                        "fonte": "nif.pt",
                        "erro": erro_msg,
                        "dados": data,
                        "tipo_erro": tipo,
                        "run_id": _run_id,
                    }

                # Por minuto / hora -> retry com espera configurada
                if acao == "retry" and deve_retry:
                    logger.warning(
                        "[api] Retry agendado nif=%s tipo=%s espera=%ss global %d/%d tipo %d/%d (tratado por error_handler)",
                        nif, tipo, espera, tentativa_global + 1, max_global_loop + 1, tentativas_por_tipo[tipo], decisao.get("max_tipo"),
                    )
                    time.sleep(espera)
                    continue

                # Por dia / mês -> abort fatal (já logado e persistido pelo handler)
                if acao == "abort":
                    logger.error("[api] Abort por quota nif=%s tipo=%s msg='%s' global %d/%d", nif, tipo, erro_msg, tentativa_global, max_global_loop)
                    logger.debug("[api] consultar_nif(%s) -> %s ABORT (%.2fs)", nif, result, time.perf_counter() - t_total)
                    return {
                        "nif": nif,
                        "valido": validar_nif(nif),
                        "fonte": "nif.pt",
                        "erro": erro_msg,
                        "dados": data,
                        "tipo_erro": tipo,
                        "run_id": _run_id,
                    }

                # Genérico / retries esgotados -> devolve erro (já persistido)
                if acao in ("abort", "none") and not deve_retry:
                    logger.warning("[api] nif.pt result='%s' nif=%s valido=%s message='%s' tipo=%s global %d/%d", result, nif, validar_nif(nif), message, tipo, tentativa_global, max_global_loop)
                    logger.debug("[api] consultar_nif(%s) -> %s (%.2fs)", nif, result, time.perf_counter() - t_total)
                    return {
                        "nif": nif,
                        "valido": validar_nif(nif),
                        "fonte": "nif.pt",
                        "erro": erro_msg,
                        "dados": data,
                        "tipo_erro": tipo,
                        "run_id": _run_id,
                    }

            except Exception as eh_err:
                # Fallback se error_handler falhar — nunca quebrar fluxo principal
                logger.warning("[erro] Falha no error_handler: %s — fallback para lógica antiga", eh_err)
                logger.warning("[api] nif.pt result='%s' nif=%s valido=%s message='%s'", result, nif, validar_nif(nif), message)
                logger.debug("[api] consultar_nif(%s) -> %s (%.2fs)", nif, result, time.perf_counter() - t_total)
                return {
                    "nif": nif,
                    "valido": validar_nif(nif),
                    "fonte": "nif.pt",
                    "erro": erro_msg,
                    "dados": data,
                    "run_id": _run_id,
                }

        records = data.get("records", {})
        registo = records.get(nif, records.get(list(records.keys())[0] if records else None))
        if not records:
            logger.debug("[api] records vazio nif=%s", nif)
        elif nif not in records:
            logger.debug("[api] records fallback nif=%s keys=%s", nif, list(records.keys())[:3])

        creditos = data.get("credits", {})
        logger.info(
            "[api] NIF %s válido=%s credits used=%s left=%s (%.2fs)",
            nif,
            True,
            creditos.get("used"),
            creditos.get("left"),
            time.perf_counter() - t_total,
        )
        logger.debug("[api] consultar_nif(%s) -> OK (%.2fs) run_id=%s", nif, time.perf_counter() - t_total, _run_id[:8])
        return {
            "nif": nif,
            "valido": True,
            "fonte": "nif.pt",
            "erro": None,
            "dados": registo,
            "nif_valido_formato": data.get("nif_validation"),
            "creditos": data.get("credits"),
            "run_id": _run_id,
        }

    # fallback se loop esgotar sem return
    if last_error:
        if "run_id" not in last_error:
            last_error["run_id"] = _run_id
        return last_error
    return {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt", "erro": "Erro desconhecido", "dados": None, "run_id": _run_id}


def main():
    """Ponto de entrada CLI — valida argv, garante tabela de erros e imprime JSON.

    Fluxo:

    1. ``setup_logging()`` + BANNER ``= 49`` (R1).
    2. ``init_error_table()`` idempotente (ignora falhas).
    3. Valida ``sys.argv[1]`` (``isdigit``) e loga ``validar_nif`` Mod-11
       (aviso mas não bloqueia — o request é sempre tentado).
    4. Chama :func:`consultar_nif` e faz ``print(json.dumps(..., indent=2,
       ensure_ascii=False))`` em ``stdout``.
    5. BOX de resumo (``- 49`` + ``| ... |``) e TIMING ``Aplicação concluída
       em %.2fs``; ``sys.exit(1)`` se ``resultado["erro"]``.

    Args:
        Nenhum — lê ``sys.argv`` diretamente. Espera ``sys.argv[1]`` com
        NIF de 9 dígitos.

    Returns:
        Não retorna — termina com ``sys.exit(0)`` em sucesso ou
        ``sys.exit(1)`` em erro. ``stdout`` contém sempre JSON válido.

    Examples:
        >>> # $ python consulta_nif.py 509442013  (doctest: +SKIP)
        >>> # {"nif": "509442013", "valido": true, "erro": null, ...}
        >>> # $ python consulta_nif.py 999  (doctest: +SKIP)
        >>> # {"erro": "NIF deve conter apenas dígitos"}

    See Also:
        :func:`validar_nif`, :func:`consultar_nif`,
        :func:`utils.error_handler.init_error_table`.
    """
    logger_main = setup_logging()
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt consulta_nif a iniciar ':=^49}")
    logger_main.info("=" * 49)
    t_app = time.perf_counter()

    # run_id — novo por execução, propagado via JSON + error_handler
    cli_run_id = extract_cli_run_id()
    _run_id = ensure_run_id(cli_value=cli_run_id)
    logger_main.info("[run] run_id=%s", _run_id)

    # Garantir tabela de erros existe antes de consultar (idempotente)
    try:
        from utils.error_handler import init_error_table
        init_error_table()
    except Exception as e:
        logger_main.warning("[erro] Falha init tabela erros: %s", e)

    if TIMEOUT and TIMEOUT > 60:
        logger_main.warning("[cfg] timeout=%ss excessivo, recomendado 10s", TIMEOUT)

    argv_clean = remove_run_id_args()
    if len(argv_clean) < 2:
        logger_main.error("[cli] Uso: python consulta_nif.py <NIF> [--run-id <uuid>] (ex: 509442013)")
        print(json.dumps({
            "erro": "Uso: python consulta_nif.py <NIF>",
            "exemplo": "python consulta_nif.py 509442013",
            "run_id": _run_id,
        }, indent=2, ensure_ascii=False))
        logger_main.info("[run] run_id=%s", _run_id)
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt consulta_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    nif = argv_clean[1].strip()
    logger_main.info("[cli] NIF recebido: %s run_id=%s", nif, _run_id[:8])

    if not nif.isdigit():
        logger_main.error("[cli] NIF deve conter apenas dígitos: '%s'", nif)
        print(json.dumps({"erro": "NIF deve conter apenas dígitos", "run_id": _run_id}, indent=2, ensure_ascii=False))
        logger_main.info("[run] run_id=%s", _run_id)
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt consulta_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    # Validação Mod-11 completa — não bloqueia mas loga
    if not validar_nif(nif):
        logger_main.warning("[valid] NIF %s falha validação Mod-11, mas request será enviado", nif)

    logger_main.debug("-" * 49)
    resultado = consultar_nif(nif, run_id=_run_id)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    if resultado.get("erro"):
        logger_main.error("[cli] Consulta falhou nif=%s erro=%s run_id=%s", nif, resultado.get("erro"), _run_id[:8])
        # Box resumo erro
        logger_main.info("-" * 49)
        logger_main.info("| Consulta falhou                             |")
        logger_main.info("|---------------------------------------------|")
        logger_main.info("| NIF         : %-30s |", nif)
        logger_main.info("| Erro        : %-30s |", str(resultado.get("erro"))[:30])
        logger_main.info("| run_id      : %-30s |", _run_id[:30])
        logger_main.info("-" * 49)
        logger_main.info("[run] run_id=%s", _run_id)
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt consulta_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    # BOX sucesso
    creditos = resultado.get("creditos", {})
    dados = resultado.get("dados", {}) or {}
    titulo = (dados.get("title") or "")[:30]
    logger_main.info("-" * 49)
    logger_main.info("| Consulta com sucesso                          |")
    logger_main.info("|---------------------------------------------|")
    logger_main.info("| NIF         : %-30s |", nif)
    logger_main.info("| Titulo      : %-30s |", titulo)
    logger_main.info("| Valido      : %-30s |", str(resultado.get("valido")))
    logger_main.info("| Creditos    : %-30s |", str(creditos.get("used")))
    logger_main.info("| run_id      : %-30s |", _run_id[:30])
    logger_main.info("-" * 49)

    logger_main.info("[run] run_id=%s", _run_id)
    logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt consulta_nif finalizado ':=^49}")
    logger_main.info("=" * 49)


if __name__ == "__main__":
    main()

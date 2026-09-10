#!/usr/bin/env python3
"""
Consulta NIF.pt — Dado um NIF, recolhe toda a informação pública e devolve JSON.

Uso:
    python consulta_nif.py <NIF>
    python consulta_nif.py 509442013

A configuração (API base, key) é lida do config.yaml e .env via config.py.
"""

import json
import logging
import sys
import time
from pathlib import Path

import requests
from config.config import get_config
from Logging.logging_orchestrator import setup_logging

logger = logging.getLogger(__name__)

cfg = get_config("consulta_nif")

API_BASE = cfg.get("api_base", "http://www.nif.pt")
API_KEY = cfg.get("NIF_PT_KEY")
TIMEOUT = cfg.get("timeout", 10)
RETRY_COUNT = cfg.get("retry_count", 1)
TEMPO_ESPERA = cfg.get("tempo_de_espera", 60)

# Aviso se timeout excessivo
if TIMEOUT and TIMEOUT > 60:
    # logger ainda pode não ter handlers nesta fase (antes de setup_logging)
    # mas a mensagem será capturada após setup no main
    pass


def validar_nif(nif: str) -> bool:
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


def consultar_nif(nif: str) -> dict:
    logger.debug(f"{' consultar_nif() ':~^49}")
    t_total = time.perf_counter()

    if not API_KEY:
        logger.error("[cfg] NIF-PT-KEY não encontrada no config/.env")
        return {
            "nif": nif,
            "valido": validar_nif(nif),
            "fonte": None,
            "erro": "NIF-PT-KEY não encontrada no .env",
            "dados": None,
        }

    url = f"{API_BASE}/"
    params = {"json": 1, "q": nif, "key": API_KEY}
    masked_key = f"***{API_KEY[-4:]}" if API_KEY and len(API_KEY) >= 4 else "***"
    logger.info("[api] GET %s?q=%s key=%s timeout=%ss", API_BASE, nif, masked_key, TIMEOUT)

    last_error = None
    for attempt in range(RETRY_COUNT + 1):
        t_req = time.perf_counter()
        try:
            logger.debug("[api] Tentativa %d/%d GET %s params q=%s", attempt + 1, RETRY_COUNT + 1, url, nif)
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
            logger.error("[api] Timeout na consulta nif.pt?q=%s após %.2fs (timeout=%s) tentativa %d/%d", nif, elapsed, TIMEOUT, attempt + 1, RETRY_COUNT + 1)
            last_error = {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt", "erro": "Timeout na consulta à API nif.pt", "dados": None}
            if attempt < RETRY_COUNT:
                logger.warning("[api] Retry em %ss (tentativa %d/%d)", TEMPO_ESPERA, attempt + 1, RETRY_COUNT + 1)
                time.sleep(TEMPO_ESPERA)
                continue
            logger.debug("[api] consultar_nif(%s) -> FAIL Timeout (%.2fs)", nif, time.perf_counter() - t_total)
            return last_error
        except requests.exceptions.RequestException as e:
            elapsed = time.perf_counter() - t_req
            logger.error("[api] Erro de rede nif.pt?q=%s: %s (%.2fs) tentativa %d/%d", nif, e, elapsed, attempt + 1, RETRY_COUNT + 1)
            last_error = {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt", "erro": f"Erro de rede: {e}", "dados": None}
            if attempt < RETRY_COUNT:
                logger.warning("[api] Retry em %ss", TEMPO_ESPERA)
                time.sleep(TEMPO_ESPERA)
                continue
            logger.debug("[api] consultar_nif(%s) -> FAIL rede (%.2fs)", nif, time.perf_counter() - t_total)
            return last_error
        except json.JSONDecodeError:
            elapsed = time.perf_counter() - t_req
            body_len = len(resp.text) if 'resp' in locals() and hasattr(resp, 'text') else 0
            logger.error("[api] Resposta não JSON de nif.pt nif=%s body_len=%d (%.2fs)", nif, body_len, elapsed)
            return {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt", "erro": "Resposta inválida (não JSON) da API", "dados": None}

        # Sucesso HTTP mas result pode ser error
        if data.get("result") != "success":
            result = data.get("result", "Erro desconhecido da API")
            message = data.get("message", "")
            # mensagem mais útil que result genérico
            erro_msg = message or result
            # Rate-limit: retry
            if "Limit per minute" in str(message) or "Limit per" in str(result):
                creditos = data.get("credits", {})
                left = creditos.get("left", {}) if isinstance(creditos.get("left"), dict) else {}
                logger.warning(
                    "[api] Rate-limit atingido nif=%s result='%s' message='%s' credits left_minute=%s tentativa %d/%d",
                    nif, result, message, left.get("minute") if isinstance(left, dict) else "[]", attempt + 1, RETRY_COUNT + 1
                )
                if attempt < RETRY_COUNT:
                    logger.warning("[api] Retry rate-limit em %ss", TEMPO_ESPERA)
                    time.sleep(TEMPO_ESPERA)
                    continue
            logger.warning("[api] nif.pt result='%s' nif=%s valido=%s message='%s'", result, nif, validar_nif(nif), message)
            logger.debug("[api] consultar_nif(%s) -> %s (%.2fs)", nif, result, time.perf_counter() - t_total)
            return {
                "nif": nif,
                "valido": validar_nif(nif),
                "fonte": "nif.pt",
                "erro": erro_msg,
                "dados": data,
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
        logger.debug("[api] consultar_nif(%s) -> OK (%.2fs)", nif, time.perf_counter() - t_total)
        return {
            "nif": nif,
            "valido": True,
            "fonte": "nif.pt",
            "erro": None,
            "dados": registo,
            "nif_valido_formato": data.get("nif_validation"),
            "creditos": data.get("credits"),
        }

    # fallback se loop esgotar sem return
    return last_error if last_error else {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt", "erro": "Erro desconhecido", "dados": None}


def main():
    logger_main = setup_logging()
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt consulta_nif a iniciar ':=^49}")
    logger_main.info("=" * 49)
    t_app = time.perf_counter()

    if TIMEOUT and TIMEOUT > 60:
        logger_main.warning("[cfg] timeout=%ss excessivo, recomendado 10s", TIMEOUT)

    if len(sys.argv) < 2:
        logger_main.error("[cli] Uso: python consulta_nif.py <NIF> (ex: 509442013)")
        print(json.dumps({
            "erro": "Uso: python consulta_nif.py <NIF>",
            "exemplo": "python consulta_nif.py 509442013"
        }, indent=2, ensure_ascii=False))
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt consulta_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    nif = sys.argv[1].strip()
    logger_main.info("[cli] NIF recebido: %s", nif)

    if not nif.isdigit():
        logger_main.error("[cli] NIF deve conter apenas dígitos: '%s'", nif)
        print(json.dumps({"erro": "NIF deve conter apenas dígitos"}, indent=2, ensure_ascii=False))
        logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
        logger_main.info("=" * 49)
        logger_main.info(f"{' nif-pt consulta_nif finalizado ':=^49}")
        logger_main.info("=" * 49)
        sys.exit(1)

    # Validação Mod-11 completa — não bloqueia mas loga
    if not validar_nif(nif):
        logger_main.warning("[valid] NIF %s falha validação Mod-11, mas request será enviado", nif)

    logger_main.debug("-" * 49)
    resultado = consultar_nif(nif)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    if resultado.get("erro"):
        logger_main.error("[cli] Consulta falhou nif=%s erro=%s", nif, resultado.get("erro"))
        # Box resumo erro
        logger_main.info("-" * 49)
        logger_main.info("| Consulta falhou                             |")
        logger_main.info("|---------------------------------------------|")
        logger_main.info("| NIF         : %-30s |", nif)
        logger_main.info("| Erro        : %-30s |", str(resultado.get("erro"))[:30])
        logger_main.info("-" * 49)
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
    logger_main.info("-" * 49)

    logger_main.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app)
    logger_main.info("=" * 49)
    logger_main.info(f"{' nif-pt consulta_nif finalizado ':=^49}")
    logger_main.info("=" * 49)


if __name__ == "__main__":
    main()

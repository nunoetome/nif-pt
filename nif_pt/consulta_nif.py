#!/usr/bin/env python3
"""
Consulta NIF.pt — Dado um NIF, recolhe toda a informação pública e devolve JSON.

Uso:
    python consulta_nif.py <NIF>
    python consulta_nif.py 509442013

A configuração (API base, key) é lida do config.yaml e .env via config.py.
"""

import sys
import json
import time
import requests
from pathlib import Path
from loguru import logger
from config.config import get_config


cfg = get_config("consulta_nif")

API_BASE = cfg.get("api_base", "http://www.nif.pt")
API_KEY = cfg.get("NIF_PT_KEY")
TIMEOUT = cfg.get("timeout", 1000)


def validar_nif(nif: str) -> bool:
    if not nif.isdigit() or len(nif) != 9:
        return False
    nif_int = int(nif)
    if nif_int == 0:
        return False
    total = sum(int(d) * (9 - i) for i, d in enumerate(nif[:8]))
    resto = total % 11
    digito_controlo = 0 if resto in (0, 1) else 11 - resto
    return digito_controlo == int(nif[8])


def _classificar_erro_api(data: dict, nif: str) -> str:
    """Classifica o erro da API e devolve uma descrição legível."""
    result = data.get("result", "")
    error = data.get("error", "")

    if result == "error":
        error_lower = error.lower()
        # NIFs privados/inexistentes
        if any(kw in error_lower for kw in ["not found", "não encontrado", "invalid", "inválido"]):
            return "NIF privado ou inexistente"
        # Limite de taxa
        if any(kw in error_lower for kw in ["limit", "rate", "quota"]):
            return "Limite de taxa atingido"
        # Erro genérico
        return error or "Erro desconhecido da API"

    return result


def consultar_nif(nif: str, max_retries: int = 3) -> dict:
    """Consulta um NIF na API nif.pt com retry automático para erros de limite."""
    if not API_KEY:
        return {
            "nif": nif,
            "valido": validar_nif(nif),
            "fonte": None,
            "erro": "NIF-PT-KEY não encontrada no .env",
            "dados": None,
        }

    url = f"{API_BASE}/"
    params = {"json": 1, "q": nif, "key": API_KEY}

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            return {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt",
                    "erro": "Timeout na consulta à API nif.pt", "dados": None}
        except requests.exceptions.RequestException as e:
            return {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt",
                    "erro": f"Erro de rede: {e}", "dados": None}
        except json.JSONDecodeError:
            return {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt",
                    "erro": "Resposta inválida (não JSON) da API", "dados": None}

        if data.get("result") != "success":
            erro_msg = _classificar_erro_api(data, nif)

            # Retry se for erro de limite
            if "Limite de taxa" in erro_msg and attempt < max_retries - 1:
                wait_time = 60 * (attempt + 1)
                logger.warning(f"[api] Limite atingido para NIF {nif}. Retry {attempt+1}/{max_retries} em {wait_time}s...")
                time.sleep(wait_time)
                continue

            return {
                "nif": nif,
                "valido": validar_nif(nif),
                "fonte": "nif.pt",
                "erro": erro_msg,
                "dados": data,
            }

        records = data.get("records", {})
        registo = records.get(nif, records.get(list(records.keys())[0] if records else None))

        return {
            "nif": nif,
            "valido": True,
            "fonte": "nif.pt",
            "erro": None,
            "dados": registo,
            "nif_valido_formato": data.get("nif_validation"),
            "creditos": data.get("credits"),
        }

    # Se todos os retries falharam
    return {
        "nif": nif,
        "valido": validar_nif(nif),
        "fonte": "nif.pt",
        "erro": f"Falhou após {max_retries} tentativas",
        "dados": None,
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "erro": "Uso: python consulta_nif.py <NIF>",
            "exemplo": "python consulta_nif.py 509442013"
        }, indent=2, ensure_ascii=False))
        sys.exit(1)

    nif = sys.argv[1].strip()

    if not nif.isdigit():
        print(json.dumps({"erro": "NIF deve conter apenas dígitos"}, indent=2, ensure_ascii=False))
        sys.exit(1)

    resultado = consultar_nif(nif)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    if resultado.get("erro"):
        sys.exit(1)


if __name__ == "__main__":
    main()

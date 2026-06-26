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
import requests
from pathlib import Path
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


def consultar_nif(nif: str) -> dict:
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
        return {
            "nif": nif,
            "valido": validar_nif(nif),
            "fonte": "nif.pt",
            "erro": data.get("result", "Erro desconhecido da API"),
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

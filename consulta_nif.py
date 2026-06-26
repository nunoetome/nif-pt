#!/usr/bin/env python3
"""
Consulta NIF.pt — Dado um NIF, recolhe toda a informação pública e devolve JSON.

Uso:
    python consulta_nif.py <NIF>
    python consulta_nif.py 509442013

A chave da API é lida do ficheiro .env (NIF-PT-KEY).
"""

import sys
import json
import requests
from pathlib import Path

# Tenta carregar .env se python-dotenv estiver instalado
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

import os

# Carrega variáveis de ambiente do ficheiro .env da pasta config
env_path = Path(__file__).parent / "config" / ".env"
if env_path.exists():
    if load_dotenv:
        load_dotenv(dotenv_path=env_path)
    else:
        # Fallback: parse manual simples
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())


API_BASE = "http://www.nif.pt"
API_KEY = os.getenv("NIF-PT-KEY")


def validar_nif(nif: str) -> bool:
    """Valida o formato de um NIF português (9 dígitos, com dígito de controlo)."""
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
    """
    Consulta a API pública do nif.pt.

    Retorna um dicionário com a estrutura:
    {
        "nif": "...",
        "valido": true/false,
        "fonte": "nif.pt",
        "dados": { ... }  # resposta completa da API
    }
    """
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
        resp = requests.get(url, params=params, timeout=15)
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

    # Extrai o registo do NIF consultado
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

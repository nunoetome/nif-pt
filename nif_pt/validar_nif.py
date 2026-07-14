#!/usr/bin/env python3
"""
Validação de NIF português — algoritmo Mod-11.

Fornece uma função que, dado um NIF, valida o dígito de controlo
e devolve um dicionário com o resultado.

Uso como módulo:
    from nif_pt.validar_nif import validar_nif
    resultado = validar_nif("503504564")

Uso como script:
    python validar_nif.py <NIF>
"""

from dataclasses import dataclass


@dataclass
class ResultadoValidacao:
    """Resultado da validação de um NIF."""

    nif: str
    valido: bool
    digito_fornecido: int
    digito_esperado: int
    primeiro_digito: int
    tipo_entidade: str
    erro: str | None


_TIPOS_ENTIDADE = {
    1: "Pessoa singular (residente)",
    2: "Pessoa singular (residente)",
    3: "Pessoa singular (residente)",
    5: "Pessoa coletiva (empresa)",
    6: "Administração pública",
    8: "Empresário em Nome Individual (ENI)",
    9: "Outras entidades",
}


def _calcular_digito_controlo(nif: str) -> int:
    """Calcula o dígito de controlo Mod-11 a partir dos primeiros 8 dígitos."""
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(d) * p for d, p in zip(nif[:8], pesos))
    resto = soma % 11
    return 0 if resto in (0, 1) else 11 - resto


def _obter_tipo_entidade(primeiro_digito: int) -> str:
    """Devolve a descrição do tipo de entidade consoante o primeiro dígito."""
    return _TIPOS_ENTIDADE.get(primeiro_digito, "Desconhecido")


def _normalizar(nif: str) -> tuple[str, str | None]:
    """
    Normaliza o input: remove espaços, aceita prefixo PT/pt.

    Devolve (nif_limpo, erro). Se erro for None, o nif_limpo tem 9 dígitos.
    """
    nif = nif.strip()

    if nif.upper().startswith("PT"):
        nif = nif[2:]

    nif = nif.strip()

    if len(nif) != 9:
        return "", f"Comprimento inválido: esperado 9 dígitos, encontrado {len(nif)}"

    if not nif.isdigit():
        return "", "Caracteres inválidos: o NIF deve conter apenas dígitos"

    return nif, None


def validar_nif(nif: str) -> ResultadoValidacao:
    """
    Valida um NIF português verificando o dígito de controlo (Mod-11).

    Aceita 9 dígitos ou prefixo PT seguido de 9 dígitos (ex.: PT503504564).

    Args:
        nif: String com o NIF a validar.

    Returns:
        ResultadoValidacao com:
            - nif: NIF limpo (sem prefixo)
            - valido: True se o dígito de controlo estiver correto
            - digito_fornecido: último dígito do NIF
            - digito_esperado: dígito calculado pelo algoritmo
            - primeiro_digito: primeiro dígito do NIF
            - tipo_entidade: descrição do tipo de entidade
            - erro: mensagem de erro se formato inválido, None se ok
    """
    nif_limpo, erro = _normalizar(nif)

    if erro:
        return ResultadoValidacao(
            nif=nif.strip(),
            valido=False,
            digito_fornecido=-1,
            digito_esperado=-1,
            primeiro_digito=-1,
            tipo_entidade="Inválido",
            erro=erro,
        )

    primeiro_digito = int(nif_limpo[0])
    digito_fornecido = int(nif_limpo[8])
    digito_esperado = _calcular_digito_controlo(nif_limpo)

    return ResultadoValidacao(
        nif=nif_limpo,
        valido=digito_fornecido == digito_esperado,
        digito_fornecido=digito_fornecido,
        digito_esperado=digito_esperado,
        primeiro_digito=primeiro_digito,
        tipo_entidade=_obter_tipo_entidade(primeiro_digito),
        erro=None,
    )


def main():
    import sys

    if len(sys.argv) < 2:
        print("Uso: python validar_nif.py <NIF>")
        sys.exit(2)

    nif = sys.argv[1]
    r = validar_nif(nif)

    if r.valido:
        print(f"Válido — {r.nif} ({r.tipo_entidade})")
        sys.exit(0)
    else:
        print(f"Inválido — {r.nif} (dígito fornecido: {r.digito_fornecido}, esperado: {r.digito_esperado})")
        sys.exit(1)


if __name__ == "__main__":
    main()

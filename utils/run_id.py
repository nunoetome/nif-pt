#!/usr/bin/env python3
"""
utils.run_id — Geração e propagação de run_id por execução.

Cada invocação do programa (qualquer variante: consulta_nif, importar_nif,
importar_nif_sqlite, main) gera um UUID v4 único que identifica essa
execução. O run_id é propagado via JSON (campo ``run_id``) de módulo para
módulo, garantindo que todas as linhas SQL inseridas na mesma execução
partilham o mesmo identificador.

Uso
---
>>> from utils.run_id import generate_run_id, get_run_id, set_run_id
>>> rid = generate_run_id()  # ex: '550e8400-e29b-41d4-a716-446655440000'
>>> set_run_id(rid)
>>> get_run_id() == rid
True

Propagação via JSON
-------------------
* ``consulta_nif`` gera e inclui ``run_id`` no dict de retorno.
* ``importar_nif{,_sqlite}`` lê ``resultado["run_id"]``; se ausente gera
  novo (retrocompatibilidade) e loga warning.
* CLI ``--run-id <uuid>`` permite override determinístico / replay.

See Also:
    :mod:`consulta_nif`, :mod:`importar_nif`, :mod:`importar_nif_sqlite`,
    :mod:`utils.error_handler`
"""

import contextvars
import logging
import uuid

logger = logging.getLogger(__name__)

# ContextVar — thread-safe e async-safe, evita global mutável
_run_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("run_id", default=None)


def generate_run_id() -> str:
    """Gera um novo run_id UUID v4.

    Returns:
        String ``xxxxxxxx-xxxx-4xxx-xxxx-xxxxxxxxxxxx`` (36 chars com hífens).

    Examples:
        >>> rid = generate_run_id()
        >>> len(rid)
        36
        >>> rid.count("-")
        4
    """
    rid = str(uuid.uuid4())
    logger.debug("[run] generate_run_id() -> %s", rid)
    return rid


def set_run_id(run_id: str | None) -> str | None:
    """Define o run_id no contexto actual.

    Args:
        run_id: UUID string ou ``None`` para limpar.

    Returns:
        O ``run_id`` definido.

    Examples:
        >>> set_run_id("550e8400-e29b-41d4-a716-446655440000")
        '550e8400-e29b-41d4-a716-446655440000'
    """
    _run_id_ctx.set(run_id)
    if run_id:
        logger.debug("[run] set_run_id(%s)", run_id)
    return run_id


def get_run_id() -> str | None:
    """Devolve o run_id do contexto actual.

    Returns:
        UUID string ou ``None`` se ainda não definido.
    """
    return _run_id_ctx.get()


def ensure_run_id(
    cli_value: str | None = None,
    payload_value: str | None = None,
) -> str:
    """Resolve o run_id com precedência CLI > payload > contexto > geração.

    Ordem de precedência:
    1. ``cli_value`` (``--run-id``) se não-vazio
    2. ``payload_value`` (``resultado["run_id"]`` do JSON) se não-vazio
    3. ContextVar actual se já definido
    4. Gera novo ``uuid4``

    O run_id resolvido é sempre guardado no contexto via :func:`set_run_id`.

    Args:
        cli_value: Valor de ``--run-id`` da linha de comandos.
        payload_value: Valor de ``run_id`` vindo do JSON stdin.

    Returns:
        UUID string resolvido (sempre não-vazio).

    Examples:
        >>> rid = ensure_run_id(payload_value="abc-123")
        >>> rid
        'abc-123'
    """
    if cli_value and cli_value.strip():
        rid = cli_value.strip()
        logger.debug("[run] ensure_run_id via cli -> %s", rid)
        set_run_id(rid)
        return rid
    if payload_value and str(payload_value).strip():
        rid = str(payload_value).strip()
        logger.debug("[run] ensure_run_id via payload -> %s", rid)
        set_run_id(rid)
        return rid
    ctx = get_run_id()
    if ctx:
        logger.debug("[run] ensure_run_id via contexto -> %s", ctx)
        return ctx
    rid = generate_run_id()
    set_run_id(rid)
    return rid


def extract_cli_run_id(argv: list[str] | None = None) -> str | None:
    """Extrai ``--run-id <valor>`` de ``argv`` sem usar ``argparse``.

    Permite parsing manual sem quebrar compatibilidade com ``sys.argv[1]``
    posicional (NIF). Suporta ``--run-id UUID`` e ``--run-id=UUID``.

    Args:
        argv: Lista de argumentos (default ``sys.argv``).

    Returns:
        Valor do ``--run-id`` ou ``None`` se não presente.

    Examples:
        >>> extract_cli_run_id(["prog", "509442013", "--run-id", "abc"])
        'abc'
        >>> extract_cli_run_id(["prog", "--run-id=xyz", "509442013"])
        'xyz'
        >>> extract_cli_run_id(["prog", "509442013"]) is None
        True
    """
    import sys

    args = argv if argv is not None else sys.argv
    for i, tok in enumerate(args):
        if tok == "--run-id" and i + 1 < len(args):
            return args[i + 1]
        if tok.startswith("--run-id="):
            return tok.split("=", 1)[1]
    return None


def remove_run_id_args(argv: list[str] | None = None) -> list[str]:
    """Devolve cópia de ``argv`` sem ``--run-id`` para parsing posicional.

    Args:
        argv: Lista de argumentos (default ``sys.argv``).

    Returns:
        Nova lista sem tokens ``--run-id``.

    Examples:
        >>> remove_run_id_args(["prog", "509442013", "--run-id", "abc"])
        ['prog', '509442013']
    """
    import sys

    args = argv if argv is not None else sys.argv
    out: list[str] = []
    skip_next = False
    for tok in args:
        if skip_next:
            skip_next = False
            continue
        if tok == "--run-id":
            skip_next = True
            continue
        if tok.startswith("--run-id="):
            continue
        out.append(tok)
    return out

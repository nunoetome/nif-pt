# Help Python — nif-pt v1.2.0

> Docstrings PEP 257 completas para `help(xxx)` / `python -m pydoc`. Verificadas com `.venv/Scripts/python.exe -c "help(...)"` em 2026-09-10 (atualizado para `cache_validator` + remoção Azure).

## 1. Como usar

```python
import consulta_nif
help(consulta_nif.validar_nif)
help(consulta_nif.consultar_nif)
help(consulta_nif.main)

from utils import error_handler, cache_validator
help(error_handler.classificar_erro)
help(error_handler.tratar_erro)
help(error_handler.guardar_erro)
help(error_handler.init_error_table)
help(error_handler.get_tempo_espera)
help(error_handler.get_max_tentativas)

help(cache_validator.is_nif_recente)
help(cache_validator.registar_ignorado)
help(cache_validator.init_cache_tables)
help(cache_validator._parse_data_consulta)

from config.config import get_config
help(get_config)

import importar_nif_sqlite
help(importar_nif_sqlite.get_db)

from utils.run_id import generate_run_id, ensure_run_id, extract_cli_run_id
help(generate_run_id)
help(ensure_run_id)

# ou via pydoc
python -m pydoc consulta_nif
python -m pydoc utils.cache_validator
python -m pydoc utils.error_handler
python -m pydoc utils.run_id
python -m pydoc config.config
```

Todos os módulos logados mascaram segredos (`***XXXX`). TAGs incluem `[cache]`.

---

## 2. `consulta_nif.validar_nif` (verificado)

```
Help on function validar_nif in module consulta_nif:

validar_nif(nif: str) -> bool
    Valida o NIF português pelo algoritmo Mod-11 da Autoridade Tributária.

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
```

Verificado: `.venv\Scripts\python.exe -c "import consulta_nif; help(consulta_nif.validar_nif)"` — OK.

---

## 3. `consulta_nif.consultar_nif` (trecho verificado)

```
Help on function consultar_nif in module consulta_nif:

consultar_nif(nif: str, run_id: str | None = None) -> dict
    Consulta a API ``nif.pt`` para o NIF dado e devolve dict normalizado.

    Faz ``GET {API_BASE}/?json=1&q=<nif>&key=<NIF_PT_KEY>`` com
    ``timeout=TIMEOUT`` e ``requests.get``. Em caso de ``result != "success"``
    delega a classificação / persistência / decisão de retry a
    :func:`utils.error_handler.tratar_erro` (rate-limit minuto/hora → retry
    ``60s/3600s``, dia/mês/paid → abort, genérico → ``none``).

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

    Raises:
        Não levanta exceções para o chamador — todos os
        ``requests.exceptions.Timeout``, ``RequestException`` e
        ``json.JSONDecodeError`` são capturados e convertidos em dict de erro.
```

> Nota v1.2.0: `main()` chama `is_nif_recente()` **antes** de `consultar_nif`; se `recente==True` devolve JSON `ignorado` sem chegar aqui.

---

## 4. `utils.cache_validator.is_nif_recente` (novo v1.2.0)

```
Help on function is_nif_recente in module utils.cache_validator:

is_nif_recente(nif: str | int, dias: int | None = None) -> tuple[bool, str | None]
    Verifica se o NIF já existe em ``nif_pt`` dentro da janela ``dias``.

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
        >>> is_nif_recente("509442013", dias=30)  # doctest: +SKIP
        (True, "2026-09-10 12:00:00")
        >>> is_nif_recente("999999999", dias=30)  # doctest: +SKIP
        (False, None)

    Notas:
        * ``data_consulta`` pode vir em ``%Y-%m-%d %H:%M:%S`` ou ISO; ambos são parseados.
        * TAG ``[cache]`` + TIMING (R9).
```

Verificado: `python -c "from utils.cache_validator import is_nif_recente; help(is_nif_recente)"` — OK.

## 5. `utils.cache_validator.registar_ignorado` (novo v1.2.0)

```
Help on function registar_ignorado in module utils.cache_validator:

registar_ignorado(nif: str | int, data_ultima_consulta: str | None, motivo: str = 'cache_recente') -> int | None
    Regista tentativa ignorada em ``nif_ignorados``.

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
```

## 6. `utils.cache_validator.init_cache_tables` (novo v1.2.0)

```
Help on function init_cache_tables in module utils.cache_validator:

init_cache_tables() -> None
    Garante que a tabela ``nif_ignorados`` existe (idempotente).

    Abre ligação via :func:`_get_connection` (que já executa DDL) e fecha
    imediatamente. Chamado no arranque de :func:`consulta_nif.main`.

    Returns:
        ``None`` — efeito colateral é criação da tabela se faltar.

    Examples:
        >>> init_cache_tables()  # doctest: +SKIP
```

## 7. `utils.error_handler.tratar_erro` (trecho verificado)

```
Help on function tratar_erro in module utils.error_handler:

tratar_erro(nif: str, data: dict, attempt: int = 0, retry_count: int = 1,
            tentativas_por_tipo: dict | None = None,
            tentativa_global: int | None = None, run_id: str | None = None) -> dict
    Ponto de entrada principal da camada de tratamento de erros.

    Recebe a mensagem de erro (dict da API), decide tipo, persiste e
    devolve instrução de ação. Suporta limites por tipo + global.

    Args:
        nif: NIF consultado
        data: dict da API (result/message/credits)
        attempt: índice da tentativa atual (legado, 0-based)
        retry_count: max retries legado
        tentativas_por_tipo: dict {tipo: count}
        tentativa_global: índice global de tentativas falhadas
        run_id: identificador da execução (propagado para guardar_erro)

    Returns:
        {
          "tipo": str,            # TIPO_*
          "acao": "retry"|"abort"|"none",
          "espera": int,
          "deve_retry": bool,
          "mensagem": str,
          "codigo": str,
          "max_tipo": int,
          "max_global": int,
          "tentativas_tipo": int,
          "tentativa_global": int
        }
```

---

## 8. `utils.error_handler.classificar_erro`

```
Help on function classificar_erro in module utils.error_handler:

classificar_erro(data: dict) -> str
    Faz parse do JSON de resposta da API e decide que tipo de erro é.

    data: dict da API (ex: {"result":"error","message":"Limit per minute...","credits":{"left":{...}}})
    Retorna uma das constantes TIPO_*
    # TIPO_RATE_LIMIT_MINUTE / HOUR / DAY / MONTH / PAID / UNKNOWN / GENERIC_ERROR
```

---

## 9. `config.config.get_config`

```
Help on function get_config in module config.config:

get_config(script_name: str) -> dict
    Devolve configuração fundida para o script dado.

    Combina, por ordem de precedência crescente:

    1. ``default`` de ``config/config.yaml`` — chaves comuns (``retry_count``,
       ``timeout``, ``tempo_*``, ``max_tentativas_*``, ``cache_*``).
    2. Bloco específico ``config.yaml[script_name]`` (``consulta_nif``,
       ``importar_nif_sqlite``) — faz *shallow merge*
       ``config.update(script_config)``.
    3. Segredos de ``config/.env`` — ``NIF-PT-KEY`` (com hífen).

    Args:
        script_name: Nome do bloco em ``config.yaml``. Valores válidos:
            ``"consulta_nif"``, ``"importar_nif_sqlite"``.

    Returns:
        Dicionário com todas as chaves fundidas. Chaves de segredos sempre
        presentes (``None`` se ``.env`` não definir).

    Examples:
        >>> get_config("consulta_nif")["api_base"]
        'http://www.nif.pt'
        >>> get_config("consulta_nif")["cache_ativo"]
        True
```

---

## 10. Outros módulos

| Módulo | Função | Help breve |
|---|---|---|
| `utils.run_id.generate_run_id` | `() -> str` | UUID v4 36 chars |
| `utils.run_id.ensure_run_id` | `(cli_value, payload_value) -> str` | Precedência `CLI > payload > ctx > gen` |
| `importar_nif_sqlite.get_db` | `() -> sqlite3.Connection` | `WAL` + `DDL nif_pt` 5c + `idx_run_id` + migração `run_id` |
| `utils.error_handler.guardar_erro` | `(nif, tipo_erro, ..., run_id) -> int\|None` | `INSERT nif_api_erros` WAL 15c |
| `utils.error_handler.init_error_table` | `() -> None` | DDL 15c idempotente |
| `utils.cache_validator._get_cache_config` | `() -> (bool,int,str)` | Lê `cache_ativo/dias/tabela` do YAML |
| `utils.cache_validator._parse_data_consulta` | `(val) -> datetime\|None` | Parse `YYYY-MM-DD HH:MM:SS` / ISO / `Z` |
| `Logging.logging_orchestrator.setup_logging` | `() -> Logger` | `RotatingFileHandler` 10MB/5000/10 + R1-R9 + TAG `[cache]` |

---

## 11. Verificação

```bash
# PowerShell
.venv\Scripts\python.exe -c "import consulta_nif; help(consulta_nif.validar_nif)"
.venv\Scripts\python.exe -c "from utils.cache_validator import is_nif_recente; help(is_nif_recente)"
.venv\Scripts\python.exe -c "import utils.error_handler; help(utils.error_handler.tratar_erro)"
.venv\Scripts\python.exe -c "from config.config import get_config; help(get_config)"
.venv\Scripts\python.exe -m pydoc consulta_nif
.venv\Scripts\python.exe -m pydoc utils.cache_validator
.venv\Scripts\python.exe -m pydoc utils.error_handler
```

Todos os exemplos acima executados em HEAD `v1.2.0` — saída sem `ModuleNotFoundError`.

---

## 12. Referências

* PEP 257 — Docstring Conventions · PEP 8 — Style Guide
* `consulta_nif.py:99` `validar_nif` · `consulta_nif.py:171` `consultar_nif` · `utils/cache_validator.py:225` `is_nif_recente` · `utils/error_handler.py:515` `tratar_erro`
* `docs/technical.md` §8 catálogo file:line

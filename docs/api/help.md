# Help Python — nif-pt v1.0.0

> Docstrings PEP 257 completas para `help(xxx)` / `python -m pydoc`. Verificadas com `.venv/Scripts/python.exe -c "help(...)"` em 2026-09-10.

## 1. Como usar

```python
import consulta_nif
help(consulta_nif.validar_nif)
help(consulta_nif.consultar_nif)
help(consulta_nif.main)

from utils import error_handler
help(error_handler.classificar_erro)
help(error_handler.tratar_erro)
help(error_handler.guardar_erro)
help(error_handler.init_error_table)
help(error_handler.get_tempo_espera)
help(error_handler.get_max_tentativas)

from config.config import get_config
help(get_config)

import importar_nif
help(importar_nif.mapear_registo)
help(importar_nif.connection_string)
help(importar_nif.colunas_tabela)

import importar_nif_sqlite
help(importar_nif_sqlite.get_db)

# ou via pydoc
python -m pydoc consulta_nif
python -m pydoc utils.error_handler
python -m pydoc config.config
```

Todos os módulos logados (`consulta_nif.py:48`, `importar_nif.py:39`, `utils/error_handler.py:139`) mascaram segredos (`***XXXX`).

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

consultar_nif(nif: str) -> dict
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

    Raises:
        Não levanta exceções para o chamador — todos os
        ``requests.exceptions.Timeout``, ``RequestException`` e
        ``json.JSONDecodeError`` são capturados e convertidos em dict de erro.
```

---

## 4. `utils.error_handler.tratar_erro` (trecho verificado)

```
Help on function tratar_erro in module utils.error_handler:

tratar_erro(nif: str, data: dict, attempt: int = 0, retry_count: int = 1,
            tentativas_por_tipo: dict | None = None,
            tentativa_global: int | None = None) -> dict
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
```

Verificado: `.venv\Scripts\python.exe -c "import utils.error_handler; help(utils.error_handler.tratar_erro)"` — OK.

---

## 5. `utils.error_handler.classificar_erro`

```
Help on function classificar_erro in module utils.error_handler:

classificar_erro(data: dict) -> str
    Faz parse do JSON de resposta da API e decide que tipo de erro é.

    data: dict da API (ex: {"result":"error","message":"Limit per minute...","credits":{"left":{...}}})
    Retorna uma das constantes TIPO_*
    # TIPO_RATE_LIMIT_MINUTE / HOUR / DAY / MONTH / PAID / UNKNOWN / GENERIC_ERROR
```

---

## 6. `config.config.get_config`

```
Help on function get_config in module config.config:

get_config(script_name: str) -> dict
    Devolve configuração fundida para o script dado.

    Combina, por ordem de precedência crescente:

    1. ``default`` de ``config/config.yaml`` — chaves comuns (``retry_count``,
       ``timeout``, ``tempo_*``, ``max_tentativas_*``).
    2. Bloco específico ``config.yaml[script_name]`` (``consulta_nif``,
       ``importar_nif_sqlite``, ``importar_nif``) — faz *shallow merge*
       ``config.update(script_config)``.
    3. Segredos de ``config/.env`` — ``AZURE_USER``,
       ``AZURE_PALAVRA_CHAVE``, ``API_TOKEN``, ``NIF-PT-KEY`` (com hífen).

    Args:
        script_name: Nome do bloco em ``config.yaml``. Valores válidos:
            ``"consulta_nif"``, ``"importar_nif_sqlite"``, ``"importar_nif"``.

    Returns:
        Dicionário com todas as chaves fundidas. Chaves de segredos sempre
        presentes (``None`` se ``.env`` não definir).

    Examples:
        >>> get_config("consulta_nif")["api_base"]
        'http://www.nif.pt'
```

---

## 7. Outros módulos

| Módulo | Função | Help breve |
|---|---|---|
| `importar_nif.mapear_registo` | `(resultado: dict) -> dict` | 36 cols `place/geo/contacts/structure/creditos` + `parse_*` |
| `importar_nif.connection_string` | `() -> str` | `DRIVER={ODBC 18};SERVER=...;Encrypt=yes` |
| `importar_nif.colunas_tabela` | `() -> list[str]` | 36 nomes |
| `importar_nif_sqlite.get_db` | `() -> sqlite3.Connection` | `WAL` + `DDL nif_pt` |
| `utils.error_handler.guardar_erro` | `(nif, tipo_erro, ...) -> int|None` | `INSERT nif_api_erros` WAL |
| `utils.error_handler.init_error_table` | `() -> None` | DDL idempotente |
| `Logging.logging_orchestrator.setup_logging` | `() -> Logger` | `RotatingFileHandler` 10MB/5000/10 + R1-R9 |

---

## 8. Verificação

```bash
# PowerShell
.venv\Scripts\python.exe -c "import consulta_nif; help(consulta_nif.validar_nif)"
.venv\Scripts\python.exe -c "import utils.error_handler; help(utils.error_handler.tratar_erro)"
.venv\Scripts\python.exe -c "from config.config import get_config; help(get_config)"
.venv\Scripts\python.exe -m pydoc consulta_nif
.venv\Scripts\python.exe -m pydoc utils.error_handler
```

Todos os exemplos acima executados em HEAD `cd83aa8` — saída sem `ModuleNotFoundError`.

---

## 9. Referências

* PEP 257 — Docstring Conventions · PEP 8 — Style Guide
* `consulta_nif.py:48` `validar_nif` · `consulta_nif.py:84` `consultar_nif` · `utils/error_handler.py:346` `tratar_erro`
* `docs/technical.md` §8 catálogo file:line

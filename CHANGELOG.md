# Changelog

Todas as alterações notáveis deste projeto serão documentadas neste ficheiro.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-PT/1.0.0/),
e este projeto adere a [Semantic Versioning](https://semver.org/lang/pt-PT/).

> **Nota sobre tags:** `v.0.1.0-alpha` contém um `.` a mais face ao SemVer (`v0.1.0-alpha` é o correto).
> Mantido por fidelidade ao git; recomenda-se `git tag v0.1.0-alpha v.0.1.0-alpha` + deprecate.

## [Unreleased]

> Nada de momento. Ver [`v2.0.0`](#200---2026-09-11) para o último **BREAKING** `cache SQLite + remoção Azure SQL` (`feature/cache-sqlite` → `release/v2.0.0`).

---

## [2.0.0] - 2026-09-11

> Branch: `feature/cache-sqlite` → `release/v2.0.0` → `dev`. Tag alvo `v2.0.0`.
> Base `v1.1.0` (`c14b945` → `v1.1.0` run_id 2026-09-11, merge `feature/add_runid`).
> SemVer **major** — **BREAKING CHANGE**: remoção total da stack Azure SQL (`importar_nif.py`, `sql/*.sql`, `pyodbc`, `AZURE_*`) + nova feature de cache SQLite (`nif_ignorados`, `utils/cache_validator.py`, `cache_ativo`).

### ⚠️ Breaking Changes

- **Stack Azure SQL descontinuado — migração obrigatória para SQLite** (`BREAKING`):
  - `importar_nif.py` (576L, mapeamento 37 colunas + `pyodbc` `stg_nunotome.nif_pt_stg`) **apagado** — qualquer `python importar_nif.py`, `import importar_nif` ou pipeline `| python importar_nif.py` quebra com `ModuleNotFoundError` / `FileNotFoundError`.
  - `sql/01_criar_tabelas.sql`, `sql/02_criar_tabela_erros.sql`, `sql/03_migracao_run_id.sql` **apagados** — DDL Azure (`NVARCHAR(36)`, `IDENTITY`, `sys.indexes`, `COL_LENGTH`) deixa de existir; `sqlcmd -i sql/*.sql` falha.
  - `requirements.txt:3` — `pyodbc>=5.0.0` **removido** (agora só `requests`, `pyyaml`, `python-dotenv`) — `pip install -r requirements.txt` já não instala ODBC; ambientes que dependem de `import pyodbc` quebram.
  - `config/config.yaml:bloco importar_nif` — chaves `sql_server`, `sql_database`, `sql_schema`, `sql_driver`, `tabela_staging` **removidas** — `get_config("importar_nif")` agora levanta `ValueError` (blocos válidos só `consulta_nif` e `importar_nif_sqlite`).
  - `config/config.py:53-110` — `AZURE_USER` / `AZURE_PALAVRA_CHAVE` removidos de `get_config()` (merge `default` + bloco script + `.env` só expõe `NIF_PT_KEY`/`API_TOKEN`), log `***XXXX` sem `AZURE_*`, docstring `Args: script_name` lista só `consulta_nif`/`importar_nif_sqlite`.
  - `config/.env.example:secção Azure SQL` removida — template agora só `NIF-PT-KEY` (+ `API_TOKEN` opcional); `.env` com `AZURE_*` é ignorado.
  - `main.py:73-78` BOX ajuda — referência `| python importar_nif.py` removida (agora só `consulta_nif.py | importar_nif_sqlite.py`).
  - Infra `kiwa-pt-operations` / schema `stg_nunotome` / `ODBC Driver 18 for SQL Server` / tabela `nif_pt_stg` **descontinuados** — sem suporte, sem migração automática.

### Removed

- **`importar_nif.py` — ficheiro completo apagado** (`importar_nif.py:1-576`):
  - `mapear_registo(resultado, run_id)` 37 colunas (`run_id` 37ª), `colunas_tabela()`/`placeholders()` 37 `?`, `valores_para_insert()`, `main()` com `pyodbc.connect(DRIVER={ODBC Driver 18} SERVER=... DATABASE=... UID=AZURE_USER PWD=AZURE_PALAVRA_CHAVE)`, `INSERT INTO nif_pt_stg (37 cols) VALUES (37 ?)` + fallback `pyodbc.Error` sem `run_id`, `BOX run_id` — tudo removido.
  - Dependência `import pyodbc` (`importar_nif.py:20` antigo) eliminada do codebase.

- **`sql/*.sql` — DDL Azure apagado**:
  - `sql/01_criar_tabelas.sql` — `CREATE TABLE stg_nunotome.nif_pt` / `nif_pt_stg` (`run_id NVARCHAR(36) NULL`, `ix_nif_pt_run_id`), `CREATE SCHEMA stg_nunotome`.
  - `sql/02_criar_tabela_erros.sql` — `CREATE TABLE stg_nunotome.nif_api_erros` (`run_id NVARCHAR(36)`, `ix_nif_api_erros_run_id`).
  - `sql/03_migracao_run_id.sql` — script idempotente `IF COL_LENGTH(...) IS NULL ALTER TABLE ADD run_id` + `IF NOT EXISTS (sys.indexes) CREATE INDEX` para `nif_pt`/`nif_pt_stg`/`nif_api_erros`.

- **`requirements.txt:4` — `pyodbc>=5.0.0` removido**:
  - Antes: `requests>=2.31.0`, `pyyaml>=6.0.1`, `python-dotenv>=1.0.0`, `pyodbc>=5.0.0` (4 linhas).
  - Agora: 3 linhas (`requirements.txt:1-3` — `requests`, `pyyaml`, `python-dotenv`).

- **`config/config.yaml:bloco importar_nif` removido**:
  - Antes (v1.1.0): bloco `importar_nif:` com `sql_server`, `sql_database`, `sql_schema`, `sql_driver`, `tabela_staging`.
  - Agora (`config/config.yaml:1-31`): só `default`, `consulta_nif` (`api_base`), `importar_nif_sqlite` (`db_path`, `tabela`).

- **`config/config.py:53-134` — limpeza Azure**:
  - `get_config()` docstring `Args: script_name` agora `consulta_nif` | `importar_nif_sqlite` (antes incluía `importar_nif`).
  - Merge `CONFIG_YAML.get("default", {}).copy()` + `CONFIG_YAML.get(script_name, {})` sem chaves `sql_*`.
  - Segredos só `API_TOKEN` + `NIF_PT_KEY` (`os.getenv("NIF-PT-KEY")` hífen intencional); removido `AZURE_USER = os.getenv("AZURE_USER")` / `AZURE_PALAVRA_CHAVE`.
  - Log `logger.info("[cfg] Segredos carregados NIF-PT-KEY=***XXXX")` sem `AZURE_*`.

- **`config/.env.example:1-11` — secção Azure removida**:
  - Antes: bloco `# Azure SQL` com `AZURE_USER`, `AZURE_PALAVRA_CHAVE`, `AZURE_SQL_SERVER`, etc.
  - Agora: só `NIF-PT-KEY=coloque_a_sua_chave_aqui` + `# API_TOKEN` opcional (11L).

- **`main.py:73-78` — BOX ajuda sem Azure**:
  - Removido `| python importar_nif.py` do BOX; mantém `| python consulta_nif.py 509442013 |` e `| python consulta_nif.py 509442013 | python importar_nif_sqlite.py |`.

### Added

- **`config/config.yaml:15-18` — defaults de cache SQLite** (`default`):
  ```yaml
  cache_ativo: true                 # bool — liga/desliga validação (fail-open se false)
  cache_antiguidade_dias: 30        # int — janela de recenticidade (dias)
  cache_tabela_ignorados: "nif_ignorados"  # str — nome tabela ignorados (sanitizado alfanum+_)
  ```
  - Lidos via `config/config.py:get_config("consulta_nif")` e fundidos em `default` (shallow merge `config.update(script_config)`); expostos em `cfg.get("cache_ativo")` etc.

- **`utils/cache_validator.py` — novo módulo de cache SQLite (407L)** (`utils/cache_validator.py:1-407`):
  - **DDL `nif_ignorados`** (`utils/cache_validator.py:44-56`):
    ```sql
    CREATE TABLE IF NOT EXISTS nif_ignorados (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        nif                     INTEGER NOT NULL,
        data_tentativa          TEXT NOT NULL DEFAULT (datetime('now')),
        data_ultima_consulta    TEXT,
        dias_desde_ultima       INTEGER,
        motivo                  TEXT NOT NULL DEFAULT 'cache_recente'
    );
    CREATE INDEX IF NOT EXISTS idx_nif_ignorados_nif ON nif_ignorados(nif);
    CREATE INDEX IF NOT EXISTS idx_nif_ignorados_data ON nif_ignorados(data_tentativa);
    ```
    - Suporte a nome custom `cache_tabela_ignorados` via `replace("nif_ignorados", tabela)` sanitizado (`tabela.replace("_","").isalnum()` senão fallback `nif_ignorados`).
  - **Helpers privados** (`utils/cache_validator.py:61-160`):
    - `_get_config() -> dict` — `from config.config import get_config; cfg=get_config("consulta_nif")` com `try/except` → `{}` + `logger.warning("[cache] Falha a ler config")` (fail-open).
    - `_get_db_path() -> Path` — resolve `cfg.get("db_path","data/nif_pt.db")` relativo a `Path(__file__).parent.parent` → absoluto, `db_path.parent.mkdir(parents=True)`.
    - `_get_cache_config() -> tuple[bool,int,str]` — `(cache_ativo:bool, cache_antiguidade_dias:int, cache_tabela_ignorados:str)` com `int()` + fallback `30`, sanitização nome.
    - `_get_connection() -> sqlite3.Connection` — `sqlite3.connect(str(db_path))`, `PRAGMA journal_mode=WAL` (logado), `executescript(DDL_IGNORADOS)` + `execute(idx_nif/idx_data)` + `commit`, `logger.debug("[cache] DDL %s garantido")`.
    - `_parse_data_consulta(val: str|None) -> datetime|None` (`utils/cache_validator.py:188-219`) — parse `"%Y-%m-%d %H:%M:%S"`, `"%Y-%m-%d %H:%M:%S.%f"`, `"%Y-%m-%dT%H:%M:%S"`, `"%Y-%m-%dT%H:%M:%S.%f"` + fallback `datetime.fromisoformat(s.replace("Z","").replace("T"," "))`, `None` se vazio/inválido.
  - **API pública**:
    - `init_cache_tables() -> None` (`utils/cache_validator.py:163-182`) — idempotente, `logger.debug("~ init_cache_tables() ~")`, `t=time.perf_counter()`, `_get_connection().close()`, `logger.debug("[cache] init_cache_tables() -> %.2fs")`.
    - `is_nif_recente(nif: str|int, dias: int|None=None) -> tuple[bool, str|None]` (`utils/cache_validator.py:225-326`) — `SELECT data_consulta FROM nif_pt WHERE nif=? ORDER BY datetime(data_consulta) DESC LIMIT 1`, compara `agora - dt_ultima` com `total_seconds()/86400 < dias` (precisão horas), `total_dias<0` (relógio futuro) → `True` por segurança, `dias<=0` → `False`, `nif_pt` inexistente / sem registo / parse fail → `(False,None)` (fail-open), TAG `[cache]` + TIMING R9, `logger.info("[cache] NIF %s ultima=%s dias_desde=%d antiguidade=%d recente=%s")`.
    - `registar_ignorado(nif, data_ultima_consulta, motivo="cache_recente") -> int|None` (`utils/cache_validator.py:329-407`) — calcula `dias_desde_ultima = (now - _parse_data_consulta(data_ultima_consulta)).days`, `INSERT INTO {tabela} (nif, data_ultima_consulta, dias_desde_ultima, motivo) VALUES (?,?,?,?)`, `cur.lastrowid`, `logger.info("[cache] Ignorado registado id=%s nif=%s ultima=%s dias_desde=%s")`, `rollback` + `logger.error("[cache] Falha ao registar")` em `sqlite3.Error`.

- **Pipeline cache — sem consumo de créditos em NIFs recentes** (ver `Changed`).

### Changed

- **`config/config.py:52-134` — só SQLite**:
  - Docstring topo `Notas: NIF-PT-KEY com hífen` mantém; `get_config()` docstring `script_name` enum agora `consulta_nif`/`importar_nif_sqlite` + `See Also: utils.cache_validator (lê cache_*)` (`config/config.py:96-97`).
  - `logger.info("[cfg] Segredos carregados NIF-PT-KEY=***{last4}")` + `logger.warning("[cfg] NIF-PT-KEY com hífen não encontrada")` sem `AZURE_*`.
  - `logger.debug("[cfg] get_config(%s) merge default+script keys=%s")` inclui `cache_ativo`, `cache_antiguidade_dias`, `cache_tabela_ignorados` quando `script_name=="consulta_nif"`.

- **`consulta_nif.py:main()` — validação cache antes de `consultar_nif` — `sys.exit(0)` sem GET** (`consulta_nif.py:527-581`):
  - Após `validar_nif(nif)` e antes de `consultar_nif(nif, run_id)`:
    ```python
    from utils.cache_validator import _get_cache_config, init_cache_tables, is_nif_recente, registar_ignorado
    cache_ativo, cache_dias, _ = _get_cache_config()  # default true/30/nif_ignorados
    if cache_ativo:
        init_cache_tables()  # idempotente, fail-open
        recente, data_ultima = is_nif_recente(nif, dias=cache_dias)
        if recente:
            registar_ignorado(nif, data_ultima)  # motivo cache_recente
            logger.info("[cache] NIF %s ignorado - ultima consulta %s dentro de %d dias", nif, data_ultima, cache_dias)
            print(json.dumps({"nif":nif,"valido":validar_nif(nif),"fonte":None,"erro":None,"dados":None,
                              "ignorado":True,"motivo":"cache_recente","data_ultima_consulta":data_ultima,
                              "cache_antiguidade_dias":cache_dias,"run_id":_run_id}, indent=2, ensure_ascii=False))
            # BOX NIF ignorado
            logger.info("| NIF ignorado - cache recente                 |")
            sys.exit(0)  # sem GET à API (fail-open, não consome créditos)
    ```
  - `else: logger.debug("[cache] cache_ativo=false -> validação ignorada")`.
  - `except Exception as e: logger.warning("[cache] Validação cache falhou: %s - prossegue para API")` — **fail-open**: qualquer falha de BD/config não quebra fluxo, prossegue para `consultar_nif` normal.
  - `stdout` JSON ignorado contém `ignorado:true`, `motivo:cache_recente`, `data_ultima_consulta` (ISO `YYYY-MM-DD HH:MM:SS` de `nif_pt.data_consulta`), `cache_antiguidade_dias`, `run_id` (herdado/propagado), `fonte:None`, `dados:None` — compatível com `importar_nif_sqlite.py` early skip.
  - BOX `| NIF ignorado - cache recente |` com `| NIF : |`, `| Ultima : |`, `| Antiguidade : 30 dias |`, `| run_id : |` + `logger.info("[run] run_id=%s")` + TIMING.

- **`importar_nif_sqlite.py:main()` — early skip se `resultado.get('ignorado')`** (`importar_nif_sqlite.py:193-208`):
  - Após `ensure_run_id(cli>payload)` e antes de `if resultado.get("erro")`:
    ```python
    if resultado.get("ignorado"):
        logger.info("[cache] NIF %s ignorado (cache_recente) ultima=%s run_id=%s - skip INSERT", nif, data_ultima, _run_id[:8])
        logger.info("| NIF ignorado - skip SQLite                         |")
        sys.exit(0)
    ```
  - Log `logger.info("[cache] skip INSERT")` + BOX `| NIF ignorado - skip SQLite |` com `NIF`, `Ultima`, `run_id`; `sys.exit(0)` sem `get_db()`/`INSERT` — evita duplicar `nif_pt` e preserva `run_id` da execução do `consulta_nif`.
  - Fluxo normal `INSERT INTO nif_pt (nif,dados,data_consulta,run_id) VALUES (?,?,?,?)` inalterado para casos não ignorados.

- **`main.py:73-78` — BOX sem Azure** (`main.py:73-78`):
  - Mantém `BANNER_APP = 49`, `BOX | ... |`, `TAG [cli][run]`, `TIMING %.2fs`; remove linha `| python importar_nif.py` (ver `Removed`).

### Notas de Migração — v1.1.0 → v2.0.0

> **BREAKING — ação obrigatória antes de `pip install -r requirements.txt` ou `python consulta_nif.py`:**

```bash
# 1. Remover dependência Azure (se instalada)
pip uninstall pyodbc -y
pip install -r requirements.txt  # agora só requests, pyyaml, python-dotenv

# 2. Remover referências a importar_nif.py / AZURE_* do teu código/CI
grep -r "importar_nif" --include="*.py" --include="*.sh" --include="*.yaml" .
grep -r "AZURE_" --include="*.py" --include="*.env*" .
grep -r "pyodbc" --include="*.py" --include="*.txt" .
# substituir:
#   python consulta_nif.py 509442013 | python importar_nif.py
# por:
#   python consulta_nif.py 509442013 | python importar_nif_sqlite.py
# ou
#   python consulta_nif.py 509442013 --run-id <uuid> | python importar_nif_sqlite.py --run-id <uuid>

# 3. Limpar config.yaml — garantir que não existe bloco importar_nif
#    válido só: default, consulta_nif, importar_nif_sqlite
cat config/config.yaml
# deve conter cache_ativo/cache_antiguidade_dias/cache_tabela_ignorados em default

# 4. Limpar .env — remover AZURE_USER, AZURE_PALAVRA_CHAVE, AZURE_SQL_*
cat config/.env
# deve conter só NIF-PT-KEY (com hífen!) e opcional API_TOKEN

# 5. DDL Azure já não é necessário — sql/*.sql apagados
#    Se precisas de histórico, recuperar de git: git show v1.1.0:sql/01_criar_tabelas.sql

# 6. Verificar get_config() válido
python -c "from config.config import get_config; print(get_config('consulta_nif').keys())"
python -c "from config.config import get_config; get_config('importar_nif')"  # deve levantar ValueError

# 7. Pipeline com cache (default 30 dias) — sem GET se recente
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
# 1ª vez: GET nif.pt -> INSERT nif_pt -> 1 row
# 2ª vez (<30d): [cache] NIF ignorado -> stdout {"ignorado":true,"motivo":"cache_recente"} -> skip INSERT (0 créditos)
cat data/nif_pt.db | sqlite3 "SELECT nif, data_consulta, run_id FROM nif_pt ORDER BY data_consulta DESC LIMIT 5;"
sqlite3 data/nif_pt.db "SELECT nif, data_tentativa, data_ultima_consulta, dias_desde_ultima, motivo FROM nif_ignorados ORDER BY data_tentativa DESC LIMIT 5;"

# Desativar cache se precisas forçar consulta (ex: NIF com dados desatualizados)
# config/config.yaml:
#   default:
#     cache_ativo: false
# ou por execução: editar yaml temporariamente; não há flag CLI (fail-open mantém compat)

# Ajustar janela
#   cache_antiguidade_dias: 7   # mais agressivo (7d)
#   cache_antiguidade_dias: 0   # desativa recenticidade (sempre consulta; dias<=0 -> nunca recente)

# Tabela ignorados custom
#   cache_tabela_ignorados: "nif_ignorados_audit"
#   -> DDL cria nif_ignorados_audit com mesmos índices idx_nif_ignorados_audit_nif/data

# Verificação cache
python -c "from utils.cache_validator import is_nif_recente, _get_cache_config; print(_get_cache_config()); print(is_nif_recente('509442013', dias=30))"
python -c "from utils.cache_validator import init_cache_tables; init_cache_tables(); print('DDL nif_ignorados OK')"
```

```sql
-- SQLite — inspeção (WAL)
SELECT name FROM sqlite_master WHERE type='table' AND name IN ('nif_pt','nif_ignorados','nif_api_erros');
PRAGMA table_info(nif_ignorados);
-- id INTEGER PK, nif INTEGER, data_tentativa TEXT DEFAULT datetime('now'), data_ultima_consulta TEXT, dias_desde_ultima INTEGER, motivo TEXT DEFAULT 'cache_recente'
SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='nif_ignorados';
-- idx_nif_ignorados_nif ON nif_ignorados(nif)
-- idx_nif_ignorados_data ON nif_ignorados(data_tentativa)
SELECT nif, datetime(data_ultima_consulta), dias_desde_ultima, motivo, datetime(data_tentativa) FROM nif_ignorados ORDER BY data_tentativa DESC LIMIT 10;
SELECT nif, datetime(data_consulta), substr(run_id,1,8) FROM nif_pt ORDER BY datetime(data_consulta) DESC LIMIT 10;

-- Limpeza manual se necessário (ex: forçar reconsulta)
DELETE FROM nif_ignorados WHERE nif=509442013;
DELETE FROM nif_pt WHERE nif=509442013; -- próxima consulta fará GET
```

```bash
# Rollback para v1.1.0 (com Azure) — se necessário
git checkout v1.1.0 -- importar_nif.py sql/ requirements.txt config/config.yaml config/config.py config/.env.example main.py
pip install "pyodbc>=5.0.0"
```

---

## [1.1.0] - 2026-09-11

> Branch: `feature/add_runid` → `release/v1.1.0` → `dev`. Tag alvo `v1.1.0`.
> Base `v1.0.0` (`c14b945` — 2026-09-10, `Merge hotfix/erro_nos_requirements into dev`).
> SemVer **minor** — nova funcionalidade `run_id` (rastreabilidade por execução), sem breaking (coluna `NULL` + fallback idempotente).

### Added

- **`utils/run_id.py` — novo módulo de rastreabilidade por execução** (`feature/add_runid` — não commitado):
  - `generate_run_id() -> str` — UUID v4 `xxxxxxxx-xxxx-4xxx-xxxx-xxxxxxxxxxxx` (36 chars c/ hífens, `uuid.uuid4()`), `logger.debug("[run] generate_run_id() -> %s")`.
  - `ContextVar[str | None] _run_id_ctx` — storage `contextvars` thread-safe/async-safe (evita global mutável).
  - `set_run_id(run_id)` / `get_run_id()` — acesso ao contexto com `logger.debug("[run] set_run_id(...)")`.
  - `ensure_run_id(cli_value, payload_value) -> str` — **precedência CLI > payload JSON > ContextVar > geração**; guarda sempre no contexto via `set_run_id`.
  - `extract_cli_run_id(argv)` — parse manual `--run-id <uuid>` e `--run-id=<uuid>` sem `argparse`, sem quebrar `sys.argv[1]` posicional (NIF).
  - `remove_run_id_args(argv) -> list[str]` — devolve cópia de `argv` sem tokens `--run-id` para parsing posicional.
  - Docstrings PEP 257 completas + `logger.debug("[run] ...")` em todos os pontos.

- **CLI `--run-id` determinístico em todos os entrypoints**:
  - `consulta_nif.py`, `importar_nif.py`, `importar_nif_sqlite.py`, `main.py` aceitam `--run-id <UUID>` para replay/debug.
  - Suporta `python consulta_nif.py 509442013 --run-id 550e8400-... | python importar_nif_sqlite.py --run-id 550e8400-...` ou herança automática via JSON quando omitido.

- **Persistência SQL — coluna `run_id` + índices + migração idempotente**:
  - `sql/01_criar_tabelas.sql` — `run_id NVARCHAR(36) NULL` em `stg_nunotome.nif_pt` e `stg_nunotome.nif_pt_stg` + `CREATE INDEX ix_nif_pt_run_id` / `ix_nif_pt_stg_run_id`.
  - `sql/02_criar_tabela_erros.sql` — `run_id NVARCHAR(36) NULL` em `stg_nunotome.nif_api_erros` + `CREATE INDEX ix_nif_api_erros_run_id`.
  - **`sql/03_migracao_run_id.sql` — novo, idempotente** — `IF COL_LENGTH('stg_nunotome.{tabela}', 'run_id') IS NULL ALTER TABLE ... ADD run_id NVARCHAR(36) NULL` + `IF NOT EXISTS (sys.indexes) CREATE INDEX ...` para `nif_pt`, `nif_pt_stg`, `nif_api_erros`; `IF NOT EXISTS (sys.schemas) CREATE SCHEMA stg_nunotome`; seguro em prod, **NO-OP** em BDs novas (01/02 já incluem).
  - **SQLite** — `importar_nif_sqlite.py` DDL `run_id TEXT` + `CREATE INDEX IF NOT EXISTS idx_nif_pt_run_id`; migração runtime `PRAGMA table_info(nif_pt)` → `ALTER TABLE ADD COLUMN run_id TEXT` se em falta + log `Migração: coluna run_id adicionada`.
  - `utils/error_handler.py` — DDL `run_id TEXT` + `DDL_ERROS_INDEX_RUNID = CREATE INDEX IF NOT EXISTS idx_nif_api_erros_run_id ...` + migração `PRAGMA table_info(nif_api_erros)` idêntica.

- **Propagação `run_id` via JSON `stdout → stdin` — mesma execução = mesmo id**:
  - `consulta_nif.consultar_nif()` inclui sempre `run_id` no dict de retorno; `main()` serializa JSON com `run_id` para `stdout`.
  - `importar_nif.py` / `importar_nif_sqlite.py` resolvem `ensure_run_id(cli_value=extract_cli_run_id(), payload_value=resultado.get("run_id"))`; se `resultado["run_id"]` ausente → `logger.warning("[run] run_id ausente no JSON — gerado novo ...")` (retrocompatível).
  - `utils/error_handler.guardar_erro(..., run_id)` e `tratar_erro(..., run_id)` resolvem `get_run_id()` se `None` e persistem `run_id` na tabela de erros.

- **Logging rastreável**:
  - TAG `[run]` em `debug/info` + `run_id[:8]` truncado em todos os logs relevantes; BOX de sucesso com `| run_id : <uuid> |`; `logger.info("[run] run_id=%s", _run_id)` em `main.py` (início/fim) e nos importadores.

### Changed

- **`consulta_nif.py` — `consultar_nif(nif, run_id: str | None = None)`**:
  - Nova assinatura com `run_id` opcional; docstring atualizada (`param run_id`, `return run_id` sempre presente, `Notes` sobre `ContextVar` e propagação).
  - `_run_id = run_id or get_run_id() or generate_run_id()` + `set_run_id(_run_id)`; `logger.debug("[run] run_id=%s nif=%s")`; todos os retornos incluem `"run_id": _run_id` (sucesso, `NIF-PT-KEY` em falta, `Timeout`, `RequestException`, resposta não JSON, `result != success`, `rate_limit_*`, `creditos esgotados`).
  - `main()` gera `run_id` único via `ensure_run_id(cli_value=extract_cli_run_id())` (antes: sem id); usa `remove_run_id_args()` para preservar `sys.argv[1]` posicional; `--run-id` CLI opcional.
  - Propaga `_run_id` para `tratar_erro(..., run_id=_run_id)`; logs `[api] ... run_id=%s` e `[cfg] ... run_id=%s`.

- **`importar_nif.py` — 36 → 37 colunas**:
  - `mapear_registo(resultado, run_id: str | None = None) -> dict` — 37ª coluna `run_id` (`_run_id = run_id or resultado.get("run_id") or get_run_id()`); docstring `36 → 37 cols`.
  - `colunas_tabela() -> list[str]` — 37 nomes (último `run_id`), ordem do DDL `sql/01_criar_tabelas.sql`; `placeholders()` gera 37 `?`; `valores_para_insert()` alinha.
  - `main()` — `cli_run_id = extract_cli_run_id()` → `set_run_id()`; `ensure_run_id(cli>payload)` após `json.loads`; loga `herdado do JSON` ou `gerado novo`; `INSERT INTO nif_pt_stg (37 cols) VALUES (37 ?)` + `commit`; **fallback** `pyodbc.Error` com `"run_id" in str(ie).lower()` → `INSERT` sem coluna + `logger.warning("[db] Coluna run_id em falta — fallback ...")` (BD antiga); `BOX run_id` e `logger.info("[run] run_id=%s")` no fim.

- **`importar_nif_sqlite.py`**:
  - DDL `run_id TEXT` + `CREATE INDEX IF NOT EXISTS idx_nif_pt_run_id`; migração runtime `PRAGMA table_info` idempotente + índice.
  - `main()` — idem `ensure_run_id(cli>payload)` + `INSERT ... (nif, dados, data_consulta, run_id) VALUES (?,?,?,?)` com fallback `OperationalError` → `INSERT` sem `run_id`; logs `debug("[run] ...")`, `info("[sqlite] INSERT ... run_id=%s")`, BOX `run_id`.

- **`utils/error_handler.py`**:
  - DDL `run_id TEXT` + `DDL_ERROS_INDEX_RUNID`; `_get_connection()` garante `DDL_ERROS` + índices + migração `PRAGMA table_info(nif_api_erros)`.
  - `guardar_erro(..., run_id: str | None = None)`: resolve `get_run_id()` se `None`; `INSERT INTO nif_api_erros (..., run_id) VALUES (..., ?)` com fallback sem coluna + `logger.info("[erro] Erro guardado ... run_id=...")`.
  - `tratar_erro(..., run_id: str | None = None)`: resolve `get_run_id()`, loga `Tipo classificado ... run_id=...`, passa `run_id` a `guardar_erro(..., run_id=run_id)` em todos os ramos (`retry_60s`, `abort_retry_esgotado`, etc.).

- **`main.py` — `run_id` por execução**:
  - `ensure_run_id(cli_value=extract_cli_run_id())` no arranque; `logger.info("[run] run_id=%s", _run_id)` (início e fim) + `[cli] NIF.pt - Recolha de dados run_id=%s` (8 chars).

- **Documentação**:
  - `README.md`, `MANUAL.md`, `docs/technical.md`, `docs/database/schema.md` atualizados para documentar fluxo `run_id` (geração → JSON → INSERT → índices + query por `run_id`).

### Notas de Migração — v1.0.0 → v1.1.0

```bash
# Azure SQL — BD existente (idempotente, seguro repetir)
sqlcmd -S <server> -d <db> -i sql/03_migracao_run_id.sql
# ou via pyodbc: executar conteúdo de 03_migracao_run_id.sql

# Novas BDs — já incluído em 01/02, 03 é NO-OP
sqlcmd -S <server> -d <db> -i sql/01_criar_tabelas.sql
sqlcmd -S <server> -d <db> -i sql/02_criar_tabela_erros.sql

# SQLite — automático no arranque (PRAGMA table_info + ALTER TABLE se falta)
# Manual, se necessário:
sqlite3 nif.db "ALTER TABLE nif_pt ADD COLUMN run_id TEXT; CREATE INDEX IF NOT EXISTS idx_nif_pt_run_id ON nif_pt(run_id);"
sqlite3 nif.db "ALTER TABLE nif_api_erros ADD COLUMN run_id TEXT; CREATE INDEX IF NOT EXISTS idx_nif_api_erros_run_id ON nif_api_erros(run_id);"

# Verificação
# Azure:
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME='run_id';
SELECT name FROM sys.indexes WHERE name LIKE 'ix_%run_id';
# SQLite:
PRAGMA table_info(nif_pt); PRAGMA table_info(nif_api_erros);
```

```sql
-- Query por execução (rastreabilidade)
SELECT * FROM stg_nunotome.nif_pt WHERE run_id = '550e8400-e29b-41d4-a716-446655440000';
SELECT * FROM stg_nunotome.nif_pt_stg WHERE run_id = '...';
SELECT * FROM stg_nunotome.nif_api_erros WHERE run_id = '...';
-- SQLite
SELECT * FROM nif_pt WHERE run_id = '...';
SELECT * FROM nif_api_erros WHERE run_id = '...';
```

```bash
# Pipeline com run_id herdado (recomendado)
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
python consulta_nif.py 509442013 | python importar_nif.py

# Replay determinístico
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000 | python importar_nif_sqlite.py --run-id 550e8400-e29b-41d4-a716-446655440000
python consulta_nif.py 509442013 --run-id=550e8400-e29b-41d4-a716-446655440000 > out.json
cat out.json | python importar_nif.py --run-id 550e8400-e29b-41d4-a716-446655440000
```

---

## [1.0.0] - 2026-09-10

> Tag: `v1.0.0` → commit `c14b945` Merge `hotfix/erro_nos_requirements` into `dev` (base `58c9478` — `v0.2.0-beta`).
> Anterior `v0.2.0-beta` (`4123c1a` em `prod`). SemVer **major** — consolida *error-handler* + correções `requirements` + docs.

### Added

- `feat(error-handler): camada de tratamento de erros da API nif.pt` (`d812901` + `cd83aa8`):
  - `utils/error_handler.py` — classificação `rate_limit_minute/hour/day/month`, `creditos_esgotados`, `nif_invalido`, `erro_generico`; `tratar_erro()` com limites por tipo (`tentativas_por_tipo`) + global (`tentativa_global`, `RETRY_COUNT`, `TEMPO_ESPERA`), `guardar_erro()` em `nif_api_erros` (SQLite WAL, `LEFT` credits, `dados_json`, `acao`).
  - Integração em `consulta_nif.py` — retry com espera configurada, persistência de erros e logging `[erro]` + TIMING R9.
- `docs: documentação técnica e guias help Python com docstrings PEP 257` (`9a84fc5`):
  - `docs/` — arquitetura, BD, API, guias; `config/.env.example`; docstrings PEP 257 em `consulta_nif`, `importar_nif*`, `error_handler`.
- `README.md`, `MANUAL.md` v2 — reescrita (15 capítulos, 7 diagramas, dual-shell).

### Changed

- `refactor: logging estruturado` (`808f837` — parte):
  - `Logging/logging_orchestrator.py` — `setup_logging()` com `BANNER_APP` (`= 49`), `BANNER_SECÇÃO` (`- 49`), `BOX` (`| ... |`), TAGs `[api][db][erro][io][cfg]`, TIMING `%.2fs` (R9).

### Fixed

- `fix: corrigir erro nos requirements e implementar logging estruturado` (`808f837` + Unreleased `hotfix/erro_nos_requirements`):
  - `requirements.txt`: `yaml` → `pyyaml` (`yaml` é placeholder inexistente; causava `ModuleNotFoundError` em env limpo); adiciona `python-dotenv` e `pyodbc` já importados (`config/config.py:4`, `importar_nif.py:20`) mas não declarados; versões mínimas `requests>=2.31.0`, `pyyaml>=6.0.1`, `python-dotenv>=1.0.0`, `pyodbc>=5.0.0`.

### Migração v0.2.0-beta → v1.0.0

```bash
pip uninstall yaml -y  # se instalado por engano
pip install -r requirements.txt
```

---

## [0.2.0-beta] - 2026-06-26

> Tag: `v0.2.0-beta` → commit `4123c1a` Merge `release/v0.2.0-beta` into `prod` (merge `58c9478` em `dev`).

### ⚠️ Breaking Changes
- **SQLite — `importar_nif_sqlite.py` passa a guardar JSON bruto** (`069f356`): tabela `nif_pt` agora `id INTEGER PK AUTOINCREMENT, nif INTEGER, dados TEXT (JSON), data_consulta TEXT`. Remove ~40 colunas normalizadas (`title`, `address`, `geo_*`, `contacts_*`, `structure_*`, `cae`, `creditos_*`). Qualquer `SELECT` analítico quebra.
- **`config/config.yaml` reescrito 156 → 27 linhas** (`3821c03`): removida secção `TED` (`ted.*`, `sparql`, `rate_limits`). Quem lia `ted.*` ou `sql_server_azure_*` tem de migrar para `consulta_nif.*`, `importar_nif_sqlite.*`, `importar_nif.*`.
- **PK staging:** `nif_pt_stg` deixa de `PRIMARY KEY (nif, data_staging)` → `id BIGINT IDENTITY` / `INTEGER AUTOINCREMENT` (`b085cf2`). Procedures com PK composta quebram.

### Added
- `MANUAL.md` (310L) — manual completo PT-PT: arquitetura, pipeline, `config.yaml` + `.env`, esquemas, exemplos, troubleshooting (`0390d57`).
- `config/config.py` expõe `NIF_PT_KEY` do `.env` (`3821c03`): `config["NIF_PT_KEY"] = os.getenv("NIF-PT-KEY")`.
- PK auto-increment e `data_staging` em `nif_pt_stg` (`b085cf2`).

### Changed
- `refactor: simplificar importadores — apenas tabela de staging` (`07e22a5`): `importar_nif.py` e `importar_nif_sqlite.py` inserem **sempre** em staging; merge para principal é processo externo.
- `refactor: centralizar config` (`3821c03`): scripts deixam de fazer `load_dotenv` inline → `from config.config import get_config`.
- `consulta_nif.py` (`6e9c675`): `TIMEOUT` via `config.yaml` (`cfg.get("timeout",1000)`), `API_BASE`/`API_KEY` via `get_config`.
- `config/config.yaml` novo com 3 namespaces limpos.

### Fixed
- `requirements.txt` adiciona `yaml` (depois corrigido para `pyyaml` em v1.0.0).

### Notas de Migração — v0.1.0-alpha → v0.2.0-beta

```sql
-- SQLite: backup e recriar
ALTER TABLE nif_pt RENAME TO nif_pt_legacy;
CREATE TABLE nif_pt (id INTEGER PRIMARY KEY AUTOINCREMENT, nif INTEGER NOT NULL, dados TEXT NOT NULL, data_consulta TEXT NOT NULL DEFAULT (datetime('now')));
-- Repopular via importar_nif_sqlite.py ou migrar JSON
```

```sql
-- Azure SQL: recriar PK staging
-- Aplicar sql/01_criar_tabelas.sql — ALTER TABLE stg_nunotome.nif_pt_stg ADD id BIGINT IDENTITY(1,1)
```

---

## [0.1.0-alpha] - 2026-06-26

> Tag `v.0.1.0-alpha` → commit `412d133` Merge `feature/vibe_coding` into `dev`.

### Added
- `feat: scripts de consulta e importação NIF` (`e76c847`):
  - `consulta_nif.py` — valida NIF Mod-11, consulta `http://www.nif.pt/?json=1&q=<NIF>&key=<KEY>`, retorna `{nif,valido,fonte,dados,creditos}`.
  - `importar_nif.py` — `mapear_registo()` 36 colunas, `pyodbc` Azure SQL `stg_nunotome`, lógica staging condicional.
  - `sql/01_criar_tabelas.sql` — `stg_nunotome.nif_pt` (PK `nif`, 37 cols) + `stg_nunotome.nif_pt_stg` (PK `(nif, data_staging)`).
- `feat: importador SQLite e correção path .env` (`a1708c0`): `importar_nif_sqlite.py` com `PRAGMA WAL`, DDL `nif_pt` + `nif_pt_stg`.
- `feat: dependências e gitignore` (`1beb032`): `requests`, `venv/`, `*.db`, `data/`.
- `.gitignore` + `requirements.txt` inicial.

### Infraestrutura inicial
- Commits `70d8744` projeto iniciado + `34153ab` minor commit — scaffolding.

---

## Links comparativos

[Unreleased]: https://github.com/nunoetome/nif-pt/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/nunoetome/nif-pt/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/nunoetome/nif-pt/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nunoetome/nif-pt/compare/v0.2.0-beta...v1.0.0
[0.2.0-beta]: https://github.com/nunoetome/nif-pt/compare/v.0.1.0-alpha...v0.2.0-beta
[0.1.0-alpha]: https://github.com/nunoetome/nif-pt/releases/tag/v.0.1.0-alpha

[Keep a Changelog]: https://keepachangelog.com/pt-PT/1.0.0/
[Semantic Versioning]: https://semver.org/lang/pt-PT/

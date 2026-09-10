# Changelog

Todas as alterações notáveis deste projeto serão documentadas neste ficheiro.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-PT/1.0.0/),
e este projeto adere a [Semantic Versioning](https://semver.org/lang/pt-PT/).

> **Nota sobre tags:** `v.0.1.0-alpha` contém um `.` a mais face ao SemVer (`v0.1.0-alpha` é o correto).
> Mantido por fidelidade ao git; recomenda-se `git tag v0.1.0-alpha v.0.1.0-alpha` + deprecate.

## [Unreleased]

> Nada de momento. Ver [`v1.1.0`](#110---2026-09-11) para o último feature `run_id` (`feature/add_runid` → `release/v1.1.0`).

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

[Unreleased]: https://github.com/nunoetome/nif-pt/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/nunoetome/nif-pt/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nunoetome/nif-pt/compare/v0.2.0-beta...v1.0.0
[0.2.0-beta]: https://github.com/nunoetome/nif-pt/compare/v.0.1.0-alpha...v0.2.0-beta
[0.1.0-alpha]: https://github.com/nunoetome/nif-pt/releases/tag/v.0.1.0-alpha

[Keep a Changelog]: https://keepachangelog.com/pt-PT/1.0.0/
[Semantic Versioning]: https://semver.org/lang/pt-PT/

# Changelog

Todas as alterações notáveis deste projeto serão documentadas neste ficheiro.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-PT/1.0.0/),
e este projeto adere a [Semantic Versioning](https://semver.org/lang/pt-PT/).

> **Nota sobre tags:** `v.0.1.0-alpha` contém um `.` a mais face ao SemVer (`v0.1.0-alpha` é o correto).
> Mantido por fidelidade ao git; recomenda-se `git tag v0.1.0-alpha v.0.1.0-alpha` + deprecate.

## [Unreleased]

> Branch atual: `hotfix/erro_nos_requirements` (base `58c9478` — `v0.2.0-beta`).
> Será lançado como `v0.2.1`.

### Fixed
- Corrige `requirements.txt`: `yaml` → `pyyaml` — `yaml` é pacote placeholder inexistente; `pyyaml` é o nome PyPI correto. Causava `ModuleNotFoundError` em ambiente limpo.
- Adiciona dependências em falta em `requirements.txt`: `python-dotenv` e `pyodbc` já eram `import` em `config/config.py:4` e `importar_nif.py:20` mas não estavam declaradas.

### Added
- `README.md` — porta de entrada GitHub com quickstart, badges e diagrama Mermaid.
- `config/.env.example` — template de segredos commitado (`.env` continua ignorado).
- `docs/` — documentação técnica (arquitetura, BD, API, guias).
- `CHANGELOG.md` — este ficheiro.
- `MANUAL.md` v2 — reescrita completa (15 capítulos, 7 diagramas, dual-shell PowerShell/Bash).
- `suport/favicon.ico` — asset estático (órfão, a avaliar mover para `docs/assets/`).

### Changed
- `requirements.txt` com versões mínimas: `requests>=2.31.0`, `pyyaml>=6.0.1`, `python-dotenv>=1.0.0`, `pyodbc>=5.0.0`.

### Migração Unreleased → v0.2.1

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
- `requirements.txt` adiciona `yaml` (depois corrigido para `pyyaml` em Unreleased).

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

[Unreleased]: https://github.com/nunoetome/nif-pt/compare/v0.2.0-beta...HEAD
[0.2.0-beta]: https://github.com/nunoetome/nif-pt/compare/v.0.1.0-alpha...v0.2.0-beta
[0.1.0-alpha]: https://github.com/nunoetome/nif-pt/releases/tag/v.0.1.0-alpha

[Keep a Changelog]: https://keepachangelog.com/pt-PT/1.0.0/
[Semantic Versioning]: https://semver.org/lang/pt-PT/

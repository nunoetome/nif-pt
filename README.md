# nif-pt

> Consulta de NIFs portugueses via [nif.pt](http://www.nif.pt) — validação Mod-11, pipeline Unix e persistência SQLite WAL com **validação cache** e **rastreabilidade `run_id` (UUID v4) por execução**.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-v1.2.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Pipeline](https://img.shields.io/badge/pipeline-stdin%2Fstdout-lightgrey.svg)](MANUAL.md)
[![Logging](https://img.shields.io/badge/logging-R1--R9_<<nif--pt>>-orange.svg)](docs/guides/logging.md)

## Visão Geral

Ferramenta CLI em Python que consulta a API pública `nif.pt` (`GET ?json=1&q=<NIF>&key=<KEY>`) e guarda o resultado via **pipeline Unix** (`stdout` JSON → `stdin`):

```
consulta_nif.py  ──JSON(run_id)────────>  importar_nif_sqlite.py  (SQLite WAL, 5c: JSON+run_id)
                 ──JSON ignorado───────>  nif_ignorados           (cache, 6c, sem API)
                 ──erro(run_id)────────>  nif_api_erros           (SQLite WAL, 15c auditoria+run_id)
```

* **Validação cache SQLite** (`utils/cache_validator.py:407` + `config/config.yaml:15` `cache_ativo/cache_antiguidade_dias/cache_tabela_ignorados`) — antes de `requests.get`, `consulta_nif.py:529` `is_nif_recente(nif, dias)` verifica `nif_pt` (`SELECT data_consulta ... ORDER BY datetime(data_consulta) DESC LIMIT 1`); se `total_dias < antiguidade` → `registar_ignorado()` em `nif_ignorados` + `stdout` JSON `{ignorado:true, motivo:"cache_recente", data_ultima_consulta, cache_antiguidade_dias}` + `sys.exit(0)` sem gastar créditos; `importar_nif_sqlite.py:194` faz early skip se `ignorado`.
* **Rastreabilidade `run_id`** (`utils/run_id.py:41` `generate_run_id()` UUID v4) — gerado por execução (`consulta_nif.py:481` `ensure_run_id()` + `--run-id`), propagado via `stdout` JSON (`run_id`) → `stdin` importador, persistido em `nif_pt.run_id TEXT` e `nif_api_erros.run_id TEXT` com índice (`importar_nif_sqlite.py:102` / `utils/error_handler.py:153` migração idempotente).
* **Validação** Mod-11 da AT (`consulta_nif.py:99` `validar_nif`) antes de consumir créditos.
* **Resiliência:** `utils/error_handler.py` (806L) classifica `rate_limit_minute/hour/day/month/paid` → `retry 60s/3600s` vs `abort`, persiste sempre em `nif_api_erros` SQLite `PRAGMA WAL` (15c com `run_id`) com limites `max_tentativas_global 5 / minuto 3 / hora 2 / dia 0 / mes 0` em `config.yaml`.
* **SQLite** `data/nif_pt.db` WAL — 3 tabelas: `nif_pt` (5 cols: `id, nif, dados, data_consulta, run_id`), `nif_api_erros` (15 cols: 14 + `run_id` + `idx_run_id`), `nif_ignorados` (6 cols: `id, nif, data_tentativa, data_ultima_consulta, dias_desde_ultima, motivo` + 2 índices).
* **Logging** estruturado `Logging/logging_orchestrator.py` (580L) — `RotatingFileHandler` 10 MB/5000/10, prefixo `<<nif-pt>>`, `log_files/nif_pt.log`, estilos R1–R9 (`BANNER = 49`, `BOX`, `TAG [api][valid][cfg][db][sqlite][io][map][erro][rate-limit][cache][run]`, `TIMING %.2fs`).

Sem dependências Azure — apenas `requests`, `pyyaml`, `python-dotenv` + `sqlite3` stdlib.

Ver [MANUAL.md](MANUAL.md) (v1.2.0 + `cache` + `run_id`) para manual completo e [docs/technical.md](docs/technical.md) para arquitetura técnica com Mermaid.

## Quickstart (3 comandos)

```powershell
# 1. Ambiente — PowerShell (Windows)
py -m venv .venv
.\.venv\Scripts\Activate.ps1
# se bloquear: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements.txt
# requirements.txt: requests>=2.31.0, pyyaml>=6.0.1, python-dotenv>=1.0.0

# Git Bash (MINGW64) — alternativa:
# python -m venv .venv && source .venv/Scripts/activate

# 2. Configurar segredos
Copy-Item config\.env.example config\.env
# Editar config\.env -> NIF-PT-KEY=xxxxx  (com hífen! obter em http://www.nif.pt/contactos/api/)

# 3. Consultar e guardar
python consulta_nif.py 509442013
python consulta_nif.py 509442013 | python importar_nif_sqlite.py

# 2ª execução dentro de 30 dias → cache (sem API):
python consulta_nif.py 509442013
# stdout: {"ignorado": true, "motivo": "cache_recente", "data_ultima_consulta": "2026-09-10 12:00:00", ...}
# stderr: <<nif-pt>> [cache] NIF 509442013 ignorado - ultima consulta 2026-09-10 12:00:00 dentro de 30 dias

# Help Python (PEP 257)
python -c "import consulta_nif; help(consulta_nif.validar_nif)"
python -c "from utils.error_handler import tratar_erro; help(tratar_erro)"
python -c "from utils.cache_validator import is_nif_recente; help(is_nif_recente)"
```

## Arquitetura

```mermaid
graph LR
    U[Utilizador<br/>NIF 9 dígitos] --> C[consulta_nif.py<br/>validar Mod-11 + cache<br/>requests + retry<br/>run_id UUID v4]
    C -->|cache hit| IG[(nif_ignorados<br/>6c cache_recente<br/>WAL)]
    C -->|stdout JSON run_id<br/>ensure_ascii=False| S[importar_nif_sqlite.py<br/>JSON bruto WAL 5c<br/>early skip ignorado]
    C -->|tipo_erro + run_id| E[(nif_api_erros<br/>SQLite 15c run_id idx)]
    C -->|cache miss| API[(nif.pt<br/>GET ?json=1)]
    S --> DB[(data/nif_pt.db<br/>nif_pt 5c + nif_api_erros 15c<br/>+ nif_ignorados 6c<br/>PRAGMA WAL)]
    CV[utils/cache_validator.py<br/>is_nif_recente + registar_ignorado<br/>DDL nif_ignorados 6c] -. cache .-> C
    R[utils/run_id.py<br/>generate_run_id + ContextVar<br/>ensure --run-id > payload > ctx > uuid] -. run_id .-> C & S & E
    CFG[config.yaml + .env<br/>get_config merge] -.-> C & S & E & CV
    LOG[logging_orchestrator<br/>R1-R9 <<nif-pt>> [cache][run]] -.-> C & S & E & CV
```

* **Configuração centralizada:** `config/config.yaml` (31L, 14 chaves default incl. `cache_*`) + `config/.env` (segredos) via `config/config.py:get_config()` (`config/config.py:30`).
* **Help Python:** docstrings PEP 257 em todos os módulos — `help(consulta_nif.validar_nif)`, `help(utils.cache_validator.is_nif_recente)` (ver `docs/api/help.md`).

## Stack e requisitos

| Dependência | Versão | Instalação | Obrigatória |
|-------------|--------|------------|-------------|
| Python | `>=3.11` | https://www.python.org/downloads/ | ✅ |
| `requests` | `>=2.31.0` | `pip install -r requirements.txt` | ✅ |
| `pyyaml` | `>=6.0.1` | idem | ✅ |
| `python-dotenv` | `>=1.0.0` | idem | ✅ |
| `sqlite3` | stdlib | — | ✅ |
| Chave `nif.pt` | — | http://www.nif.pt/contactos/api/ | ✅ |

> Sem `pyodbc`, sem `ODBC Driver 18`, sem Azure SQL.

## Estrutura do Projeto

```
nif-pt/
├── consulta_nif.py               # 626L — validar Mod-11 + cache is_nif_recente + GET ?json=1 + retry + run_id + BOX
├── importar_nif_sqlite.py        # 285L — JSON bruto → SQLite WAL (5c) + early skip ignorado + run_id + migração
├── utils/cache_validator.py      # 407L — DDL nif_ignorados 6c + 2 índices + is_nif_recente() + registar_ignorado() + init_cache_tables()
├── utils/run_id.py               # 191L — generate_run_id() UUID v4 + ContextVar + ensure_run_id(CLI>payload>ctx>gen) + --run-id parse
├── utils/error_handler.py        # 806L — classificar + tratar + guardar_erro(...,run_id) + init_error_table (15c run_id)
├── main.py                       # 92L — ensure_run_id() por execução
├── Logging/logging_orchestrator.py # 580L — RotatingFileHandler 10MB/5000/10, R1-R9, <<nif-pt>>, nif_pt.log, TAG [cache][run]
├── config/
│   ├── config.py                 # 134L — get_config() merge default+script+.env, *** mascarado, cache_* documentado
│   ├── config.yaml               # 31L — default (14 chaves: 11 resiliência + 3 cache) + 2 blocos
│   └── .env.example              # template (commitado) — .env com NIF-PT-KEY hífen (não versionar)
├── docs/
│   ├── technical.md              # v1.2.0 — C4 + sequência cache + ER (3 tabelas) + catálogo file:line + ADRs
│   ├── api/help.md               # Help Python verificado (help(validar_nif), help(is_nif_recente), help(generate_run_id))
│   ├── architecture/             # C4 + diagramas Mermaid (cache + run_id)
│   ├── database/                 # ER 5/15/6c + catálogo + ddl-history
│   ├── api/nif-pt-api.md         # Contrato nif.pt
│   └── guides/                   # instalação, logging R1-R9, run_id, cache
├── data/nif_pt.db                # gerado, WAL, ignorado (.gitignore) — 3 tabelas
├── log_files/nif_pt.log          # gerado, RotatingFileHandler, ignorado
├── requirements.txt              # 3 deps pinadas (requests, pyyaml, python-dotenv)
├── CHANGELOG.md                  # v1.2.0 (2026-09-10)
└── MANUAL.md                     # manual de utilizador v1.2.0 (15 capítulos, cache + run_id)
```

## Configuração

**`config/config.yaml` (31L):**

```yaml
default:
  retry_count: 1
  timeout: 10
  tempo_de_espera: 60
  tempo_espera_minuto: 60
  tempo_espera_hora: 3600
  max_tentativas_global: 5
  max_tentativas_minuto: 3
  max_tentativas_hora: 2
  max_tentativas_dia: 0
  max_tentativas_mes: 0
  max_tentativas_paid: 0
  cache_ativo: true
  cache_antiguidade_dias: 30
  cache_tabela_ignorados: "nif_ignorados"
consulta_nif:
  api_base: "http://www.nif.pt"
importar_nif_sqlite:
  db_path: "data/nif_pt.db"
  tabela: "nif_pt"
```

| Chave cache | Onde usada | Descrição |
|-------------|------------|-----------|
| `cache_ativo` | `consulta_nif.py:532` + `utils/cache_validator.py:113` | `true` liga validação cache antes de API |
| `cache_antiguidade_dias` | `consulta_nif.py:539` `is_nif_recente(nif, dias)` | janela recenticidade (dias); `<=0` desliga |
| `cache_tabela_ignorados` | `utils/cache_validator.py:119` | nome tabela ignorados (sanitizado `alnum+_`) |

**`config/.env`** (criar de `.env.example`):

```env
NIF-PT-KEY=coloque_aqui          # com hífen — os.getenv("NIF-PT-KEY")
# API_TOKEN=opcional
```

## Exemplos

```powershell
# Só consultar (JSON stdout, stderr com BOX/TAG/TIMING, inclui run_id)
python consulta_nif.py 509442013 > resultado.json
Get-Content resultado.json | ConvertFrom-Json | Format-List  # campo run_id: UUID v4

# Guardar em SQLite (run_id propagado via JSON run_id)
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
# Ver rastreabilidade:
# sqlite3 data/nif_pt.db "SELECT nif, substr(run_id,1,8), data_consulta FROM nif_pt ORDER BY data_consulta DESC LIMIT 3;"

# Cache — 2ª consulta dentro de 30 dias não vai à API
python consulta_nif.py 509442013
# {"nif":"509442013","ignorado":true,"motivo":"cache_recente","data_ultima_consulta":"2026-09-10 12:00:00","cache_antiguidade_dias":30,"run_id":"..."}
# sqlite3 data/nif_pt.db "SELECT nif, data_ultima_consulta, motivo FROM nif_ignorados ORDER BY data_tentativa DESC LIMIT 3;"

# Desligar cache para forçar refresh
# config.yaml -> cache_ativo: false  ou  cache_antiguidade_dias: 0
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000 | python importar_nif_sqlite.py

# Importador ignora payload cache_recente (early skip)
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
# stderr: [cache] NIF 509442013 ignorado (cache_recente) ultima=... - skip INSERT

# Batch com rate-limit + cache (cada iteração gera run_id único; agrupar por run_id para auditoria)
Get-Content nifs.txt | ForEach-Object { python consulta_nif.py $_ | python importar_nif_sqlite.py; Start-Sleep -Seconds 1 }

# Validar sem gastar créditos
python -c "from consulta_nif import validar_nif; print(validar_nif('509442013'))"  # True
python -c "from utils.cache_validator import is_nif_recente; print(is_nif_recente('509442013', dias=30))"
```

## Logging (R1–R9)

`log_files/nif_pt.log` com `RotatingFileHandler` (10 MB / 5000 recs / 10 backups), prefixo `<<nif-pt>>`, `stderr` não quebra pipe:

```
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ========= nif-pt consulta_nif a iniciar =========
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - INFO - [cache] NIF 509442013 ultima=2026-09-10 12:00:00 dias_desde=0 antiguidade=30 recente=True (0.02s)
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [cache] NIF 509442013 ignorado - ultima consulta 2026-09-10 12:00:00 dentro de 30 dias
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | NIF ignorado - cache recente                 |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | run_id      : 550e8400-e29b-41d4-a716-...  |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - Aplicação concluída em 0.05s
```

Ver `docs/guides/logging.md` e `docs/technical.md` §11 (logging) + §10c (cache).

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [MANUAL.md](MANUAL.md) | Manual de utilizador v1.2.0 + `cache` + `run_id` (15 caps + pipeline cache, payload ignorado, `cache_ativo`) |
| [docs/technical.md](docs/technical.md) | Documentação técnica v1.2.0 — C4, sequência cache, ER 3 tabelas, catálogo file:line, ADRs |
| [docs/api/help.md](docs/api/help.md) | Help Python (PEP 257) — `help(validar_nif)`, `help(is_nif_recente)`, `help(generate_run_id)` |
| [docs/architecture/architecture.md](docs/architecture/architecture.md) | Arquitetura C4 + 10 ADRs (ADR-009 run_id, ADR-010 cache) |
| [docs/database/schema.md](docs/database/schema.md) | ER + catálogo 5/15/6c + `nif_ignorados` DDL + índices cache |
| [docs/api/nif-pt-api.md](docs/api/nif-pt-api.md) | Contrato API nif.pt |
| [CHANGELOG.md](CHANGELOG.md) | Histórico v0.1.0-alpha → v1.2.0 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Guia de contribuição |
| [SECURITY.md](SECURITY.md) | Gestão de segredos |

## Troubleshooting rápido

| Erro | Causa | Solução |
|------|-------|---------|
| `NIF-PT-KEY não encontrada` | `.env` em falta ou `NIF_PT_KEY` sem hífen | `config/.env` deve ter `NIF-PT-KEY=` com hífen (`config/config.py:120`) |
| `Limit per minute` | Quota minuto | Aguarda 60s (auto-retry `max 3`), ver `nif_api_erros` |
| `Limit per day/month` | Quota diária/mensal | Abort — `max 0`, ver `log_files/nif_pt.log` BOX fatal |
| `database is locked` | Concorrência SQLite | Já WAL (`importar_nif_sqlite.py:95` + `utils/cache_validator.py:142`); evitar writes paralelos |
| `NIF ignorado - cache recente` | NIF consultado há < `cache_antiguidade_dias` | Esperar janela expirar ou `cache_ativo: false` / `cache_antiguidade_dias: 0` para forçar refresh |
| `ModuleNotFoundError: yaml` | `requirements.txt` antigo | `pip install pyyaml` |

Ver [MANUAL.md §13](MANUAL.md#13-resolução-de-problemas-troubleshooting) para lista completa.

## Changelog

`v1.2.0` (unreleased) — **validação cache SQLite + remoção Azure**: `utils/cache_validator.py` (407L, `nif_ignorados` 6c + `is_nif_recente` + `registar_ignorado` + `init_cache_tables`), `consulta_nif.py:529` cache antes de API com payload `{ignorado:true, motivo:cache_recente}`, `importar_nif_sqlite.py:194` early skip ignorado, `config.yaml` `cache_ativo/cache_antiguidade_dias/cache_tabela_ignorados`, removido `importar_nif.py` (576L), `sql/01_criar_tabelas.sql`/`02_criar_tabela_erros.sql`/`03_migracao_run_id.sql`, `pyodbc`, `AZURE_*` de `config.py`/`.env.example`, stack só SQLite WAL 3 tabelas (5/15/6c).
`v1.1.0` (2026-09-11) — **rastreabilidade `run_id`**: `utils/run_id.py` (UUID v4 + `ContextVar` + `--run-id`), `consulta_nif.py:consultar_nif(nif, run_id)` inclui `run_id` em todos os JSON, `importar_nif_sqlite.py` DDL `run_id TEXT` + migração idempotente + `INSERT` com `run_id`.
`v1.0.0` (2026-09-10) — primeiro stable: `error_handler` + `nif_api_erros` + `logging_orchestrator`. Ver [CHANGELOG.md](CHANGELOG.md).

## Licença

MIT — ver `LICENSE` (a criar).

## Contacto

Repositório: `https://github.com/nunoetome/nif-pt` — Issues e PRs bem-vindos. Chave API: http://www.nif.pt/contactos/api/

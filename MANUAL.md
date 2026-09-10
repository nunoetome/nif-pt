# Manual de Instruções — nif-pt v1.1.0 (run_id)

> Ferramenta Python para consulta de NIFs portugueses via [nif.pt](http://www.nif.pt) (`?json=1`) com validação Mod-11, pipeline Unix e persistência SQLite WAL / Azure SQL + camada resiliente de rate-limit + **rastreabilidade `run_id` (UUID v4) por execução**.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-v1.0.0-blue.svg)](CHANGELOG.md)

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura e Pipeline](#2-arquitetura-e-pipeline)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Instalação](#4-instalação)
5. [Configuração](#5-configuração)
6. [Utilização — Modos de Operação](#6-utilização--modos-de-operação)
7. [Esquemas de Base de Dados](#7-esquemas-de-base-de-dados)
8. [Referência CLI](#8-referência-cli)
9. [Referência de Dados e JSON](#9-referência-de-dados-e-json)
10. [Códigos de Erro e Saída](#10-códigos-de-erro-e-saída)
11. [Logging](#11-logging)
12. [Exemplos Práticos (PowerShell & Bash)](#12-exemplos-práticos-powershell--bash)
13. [Resolução de Problemas (Troubleshooting)](#13-resolução-de-problemas-troubleshooting)
14. [FAQ](#14-faq)
15. [Anexos](#15-anexos)

---

## 1. Visão Geral

### 1.1 Objetivo e âmbito

`nif-pt` consulta a base pública do portal `nif.pt` (`GET ?json=1&q=<NIF>&key=<KEY>`) e guarda o resultado localmente (SQLite WAL) e/ou remotamente (Azure SQL). Destina-se a pessoas coletivas com registo público; NIFs de pessoas singulares ou recentes podem devolver `No records found`.

Novidade `v1.0.0`: camada `utils/error_handler.py` (806L) classifica erros de quota, persiste em `nif_api_erros` (dual SQLite/Azure, 15c com `run_id`) e aplica `retry 60s` (minuto) / `3600s` (hora) com limites `max_tentativas_global 5 / minuto 3 / hora 2 / dia 0 / mes 0`.
Novidade `v1.1.0`: **rastreabilidade `run_id`** — `utils/run_id.py` (191L) `generate_run_id()` UUID v4 + `ContextVar` + `ensure_run_id(CLI>payload>ctx>gen)`, `consulta_nif.py:consultar_nif(nif, run_id)` inclui `run_id` em todos os JSON, `importar_nif(_sqlite).py` persiste `run_id` (5c/38c/41c/15c) com `ALTER TABLE` idempotente + `INDEX run_id`, CLI `--run-id` determinístico, migração `sql/03_migracao_run_id.sql`.

### 1.2 Funcionalidades

| ID | Funcionalidade | Estado | Ficheiro |
|----|----------------|--------|----------|
| RF-01 | Validar NIF Mod-11 | ✅ | `consulta_nif.py:99` `validar_nif()` |
| RF-02 | Consultar `nif.pt` (`?json=1&q=&key=`, timeout 10s) | ✅ | `consulta_nif.py:272` `requests.get` |
| RF-03 | JSON normalizado (`valido/fonte/erro/dados/creditos/tipo_erro/run_id`) | ✅ | `consulta_nif.py:237` + `utils/run_id.py:87` |
| RF-04 | Guardar JSON bruto SQLite WAL (5c com `run_id`) | ✅ | `importar_nif_sqlite.py:66` `get_db()` + `utils/run_id.py:185` |
| RF-05 | Normalizar 37 cols (36+`run_id`) → Azure `nif_pt_stg` | ✅ | `importar_nif.py:223` `mapear_registo(...,run_id)` |
| RF-06 | Pipeline `stdin/stdout` + `exit 0/1` com `run_id` | ✅ | `sys.stdin.read()` + `utils/run_id.py:132` `--run-id` |
| RF-07 | Camada `error_handler` (6 tipos, retry/abort, `nif_api_erros` 15c `run_id`) | ✅ | `utils/error_handler.py:515` `tratar_erro(...,run_id)` |
| RF-08 | Logging R1-R9 `<<nif-pt>>` `RotatingFileHandler` 10MB/5000/10 + TAG `[run]` | ✅ | `Logging/logging_orchestrator.py:226` |
| RF-09 | `help()` PEP 257 em todos os módulos | ✅ | `docs/api/help.md` |
| RF-10 | Rastreabilidade `run_id` UUID v4 por execução (geração+propagação+persistência+`--run-id`+migração) | ✅ | `utils/run_id.py:41` `generate_run_id()` + `sql/03_migracao_run_id.sql` |

### 1.3 Requisitos não-funcionais

* **Performance:** `timeout 10s` (`config.yaml:3`), `WAL`, `sleep 60s/3600s` em retry, índices `run_id`.
* **Segurança:** segredos só em `config/.env` (`.gitignore`), `NIF-PT-KEY` mascarada `***XXXX` em todos os logs.
* **Portabilidade:** `pathlib`, `pyodbc` ODBC 18, dual PowerShell 5.1 / Bash, `ContextVar` para `run_id`.
* **Observabilidade:** `log_files/nif_pt.log` com BOX `| NIF : ... |` + `| run_id : ... |` + TAG `[api][valid][cfg][db][sqlite][io][map][erro][rate-limit][run]` + TIMING `%.2fs` + `run_id` em todos os `INSERT`.

### 1.4 Público-alvo e limitações

Operações, compliance, data engineering. `nif.pt` é agregadora — pode estar desatualizada, com `rate-limit` (`creditos.left`) ou sem registo (`No records found` não indica NIF inválido).

### 1.5 Histórico de versões

| Versão | Data | Destaque |
|--------|------|----------|
| `v.0.1.0-alpha` | 2026-06-26 | Fundação `consulta_nif` + `importar_nif` + SQLite + DDL Azure |
| `v0.2.0-beta` | 2026-06-26 | Config centralizada, SQLite JSON bruto, `MANUAL` 310L |
| `v1.1.0` **(esta)** | 2026-09-10 | `run_id` UUID v4 191L + `consulta_nif(nif,run_id)` + importadores 37c/5c + `error_handler` 15c `run_id` + `sql/03_migracao_run_id.sql` + `--run-id` |
| `v1.0.0` | 2026-09-10 | `error_handler` 806L + `nif_api_erros` dual + `logging_orchestrator` 580L + `timeout 10s` + `max_tentativas_*` + docs 15 caps |

Ver [CHANGELOG.md](CHANGELOG.md) completo.

---

## 2. Arquitetura e Pipeline

### 2.1 Diagrama de pipeline

```mermaid
graph LR
    U[Utilizador<br/>NIF 9 dígitos --run-id] --> C[consulta_nif.py<br/>validar_nif + requests<br/>tratar_erro + run_id UUID v4]
    C -->|stdout JSON run_id<br/>ensure_ascii=False| S[importar_nif_sqlite.py<br/>JSON bruto WAL 5c run_id]
    C -->|stdout JSON run_id| A[importar_nif.py<br/>37 cols pyodbc run_id]
    C -->|erro classificado run_id| E[(nif_api_erros<br/>SQLite 15c + Azure 15c run_id)]
    S --> DB1[(data/nif_pt.db<br/>nif_pt 5c + nif_api_erros 15c<br/>PRAGMA WAL + idx run_id)]
    A --> DB2[(Azure SQL<br/>stg_nunotome.nif_pt_stg 41c run_id)]
    DB2 -. MERGE futuro .-> DB3[(stg_nunotome.nif_pt 38c PK nif run_id)]
    R[utils/run_id.py<br/>generate_run_id + ContextVar<br/>ensure CLI>payload>ctx>gen] -. run_id .-> C & S & A & E
    CFG[config.yaml 37L + .env<br/>get_config merge] -.-> C & S & A & E
    LOG[logging_orchestrator<br/>R1-R9 <<nif-pt>> [run]] -.-> C & S & A & E
```

Fonte única: [docs/technical.md](docs/technical.md) + [docs/architecture/diagrams.md](docs/architecture/diagrams.md).

### 2.2 Pipeline `stdin`/`stdout`

```
consulta_nif.py  ──JSON run_id──>  importar_nif_sqlite.py  (SQLite WAL 5c)
                 ──JSON run_id──>  importar_nif.py         (Azure SQL staging 37c)
                 ──erro run_id──>  nif_api_erros           (auditoria 15c)
```
Precedência `run_id`: `CLI --run-id` > `payload JSON run_id` > `ContextVar` > `uuid4` (`utils/run_id.py:87` `ensure_run_id()`); `main.py:60` `ensure_run_id()` por execução.

* `consulta_nif.py` só JSON em `stdout` (`consulta_nif.py:529` `json.dumps(..., indent=2, ensure_ascii=False)`) com campo `run_id` UUID v4; humanos em `stderr` (`<<nif-pt>>` + `[run]`).
* Importadores `sys.stdin.read()` → `json.loads` → `ensure_run_id(CLI>payload>ctx>gen)` (`importar_nif_sqlite.py:185` / `importar_nif.py:455`) → `INSERT (...,run_id)`; falham `exit 1` se `stdin` vazio ou `resultado.erro` existe (propagam erro sem inserir). Se `run_id` ausente no JSON, geram novo e avisam `warning [run] run_id ausente`.
* `nif_api_erros` persiste **sempre** antes de decidir `retry/abort` com `run_id` (`utils/error_handler.py:368` `guardar_erro(...,run_id)`) (ver §10).

### 2.3 Centralização de configuração

`config/config.py:30` `get_config(script_name)`:

1. `default` (`config.yaml:1` — 11 chaves `retry_count`, `timeout 10`, `tempo_*`, `max_tentativas_*`)
2. Bloco do script (`consulta_nif` / `importar_nif_sqlite` / `importar_nif`)
3. `.env` (`NIF-PT-KEY` com hífen, `AZURE_USER`, `AZURE_PALAVRA_CHAVE`, `API_TOKEN`)

```python
cfg = get_config("consulta_nif")
API_BASE = cfg.get("api_base", "http://www.nif.pt")
API_KEY  = cfg.get("NIF_PT_KEY")  # os.getenv("NIF-PT-KEY")
TIMEOUT  = cfg.get("timeout", 10)
MAX_GLOBAL = cfg.get("max_tentativas_global", 5)
```

### 2.4a Rastreabilidade `run_id` (v1.1.0)

`utils/run_id.py` (191L):

| Função | Linha | Descrição |
|--------|-------|-----------|
| `generate_run_id()` | `:41` | `str(uuid.uuid4())` — 36 chars, 4 hífens, `logger.debug [run]` |
| `set_run_id` / `get_run_id` | `:59` / `:78` | `ContextVar[str|None] _run_id_ctx` thread-safe |
| `ensure_run_id(cli_value, payload_value)` | `:87` | Precedência `CLI > payload > ContextVar > geração` + `set_run_id` |
| `extract_cli_run_id(argv)` | `:132` | Parse `--run-id UUID` e `--run-id=UUID` sem `argparse` |
| `remove_run_id_args(argv)` | `:163` | Cópia `argv` sem `--run-id` para `isdigit` posicional |

**Fluxo por script:**

* `consulta_nif.py:481` `main()` → `cli_run_id=extract_cli_run_id()` → `_run_id=ensure_run_id(cli_value)` → `logger_main.info("[run] run_id=%s", _run_id)` → `consultar_nif(nif, run_id=_run_id)` (`:238` resolve `run_id or get_run_id() or generate_run_id()` e inclui `run_id` em todos os `return`).
* `importar_nif_sqlite.py:158` / `importar_nif.py:429` → `cli_run_id=extract_cli_run_id()` → `if cli_run_id: set_run_id(...)` → após `json.loads` → `ensure_run_id(cli_value, payload_value=resultado.get("run_id"))` → `INSERT (...,run_id)` + fallback se coluna falta (`:221` / `:529`).
* `utils/error_handler.py:368` `guardar_erro(...,run_id)` + `:515` `tratar_erro(...,run_id)` — propagam `run_id` (ou `get_run_id()` se `None`) para `nif_api_erros` 15c.
* `main.py:60` `ensure_run_id(cli_value=extract_cli_run_id())` por execução.

**Persistência:** DDL `run_id TEXT` (SQLite) / `NVARCHAR(36)` (Azure) + `CREATE INDEX ...run_id` + migração idempotente (`PRAGMA table_info` + `ALTER TABLE ADD COLUMN` / `sql/03_migracao_run_id.sql` `COL_LENGTH` check) — ver §7.5.

**Exemplo:**

```powershell
# determinístico
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000 | python importar_nif_sqlite.py
# herança via JSON (sem --run-id no importador)
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000 | python importar_nif.py
# agrupar por execução
# sqlite3 data/nif_pt.db "SELECT run_id, COUNT(*) FROM nif_pt GROUP BY run_id;"
# SELECT run_id, COUNT(*) FROM stg_nunotome.nif_api_erros GROUP BY run_id;
```

Ver `docs/technical.md` §10b e `docs/database/schema.md` §8.

### 2.4b Camada de erros (v1.0.0 + run_id)

`utils/error_handler.py` (612L):

* `classificar_erro(data)` → `rate_limit_minute/hour/day/month/paid` / `generic_error` / `unknown` (mensagem `Limit per ...` + `credits.left` com `0`).
* `tratar_erro(nif, data, tentativas_por_tipo, tentativa_global)` → `{tipo, acao: retry|abort|none, espera: 60|3600|0, deve_retry, max_tipo, max_global}` com lógica `deve_retry = tenta_tipo < max_tipo && tenta_global < max_global`.
* `guardar_erro(...)` → `INSERT nif_api_erros` (14 cols, WAL) sempre.
* `init_error_table()` idempotente no arranque de `consulta_nif.py:281`.
* `get_tempo_espera()` / `get_max_tentativas()` lidos do `config.yaml`.

Fluxo `consulta_nif.py:84` `consultar_nif()`:

```
for tentativa_global in range(max_global+1):
    try: requests.get(...)
    except Timeout/RequestException: sleep 60s retry se <max_global
    if result != "success": tratar_erro() -> if retry: sleep 60s/3600s continue
                                          -> if abort: return erro+tipo_erro
    else: return sucesso
```

Ver [docs/technical.md §10](docs/technical.md#10-camada-de-erros).

### 2.5 Decisões técnicas (ADRs)

| ADR | Decisão | Justificação |
|-----|---------|--------------|
| ADR-001 | SQLite JSON bruto vs Azure 37 cols (36+`run_id`) | WAL schemaless vs analítico (run_id indexado) |
| ADR-002 | `WAL` | Mitiga `database is locked` |
| ADR-003 | `ODBC 18` + `Encrypt=yes` | Exigido Azure |
| ADR-007 | `error_handler` + `nif_api_erros` dual 15c `run_id` | Auditoria + retry `60s/3600s` vs abort + rastreabilidade por execução |
| ADR-009 | `run_id` UUID v4 + `ContextVar` + `ensure_run_id` | `CLI>payload>ctx>gen`, `--run-id` replay, índices `run_id`, sem quebrar pipe |

Ver [docs/technical.md §12](docs/technical.md#12-adrs) e [docs/architecture/architecture.md](docs/architecture/architecture.md) (9 ADRs).

---

## 3. Pré-requisitos

### 3.1 Matriz de dependências

| Dependência | Versão | Instalação | Obrigatória |
|-------------|--------|------------|-------------|
| Python | `>=3.11` | https://www.python.org/downloads/ | ✅ |
| `requests` | `>=2.31.0` | `pip install -r requirements.txt` | ✅ |
| `pyyaml` | `>=6.0.1` | idem | ✅ |
| `python-dotenv` | `>=1.0.0` | idem | ✅ |
| `pyodbc` | `>=5.0.0` | idem | Só Azure |
| `ODBC Driver 18` | 18.x | https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server | Só Azure |
| Chave `nif.pt` | — | http://www.nif.pt/contactos/api/ | ✅ |

### 3.2 Chave `NIF-PT-KEY`

1. Solicitar em http://www.nif.pt/contactos/api/ (1-2 dias por email).
2. `config/.env` → `NIF-PT-KEY=xxxxx` **com hífen** (`config/config.py:55` `os.getenv("NIF-PT-KEY")`).

### 3.3 Azure SQL (opcional)

* `kiwa-pt-operations.database.windows.net` / `kiwa-pt-operations` / `stg_nunotome` (`config.yaml:33`).
* Whitelist IP no Portal Azure → SQL → Networking.
* Verificar driver: `Get-OdbcDriver` (PS) ou `odbcinst -q -d` (Linux).
* Aplicar `sql/01_criar_tabelas.sql` (38c+41c) e `sql/02_criar_tabela_erros.sql` (15c) via SSMS/Azure Data Studio/`sqlcmd`; para BDs existentes aplicar `sql/03_migracao_run_id.sql` (idempotente `run_id`).

---

## 4. Instalação

### 4.1 Clonar

```bash
git clone https://github.com/nunoetome/nif-pt.git
cd nif-pt
git checkout v1.0.0   # stable; dev para desenvolvimento
```

### 4.2 Criar `venv`

**PowerShell (Windows — o teu caso):**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
# se bloquear: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# verificar:
Get-Command python | Format-List Source  # ...\nif-pt\.venv\Scripts\python.exe
```

**Git Bash (MINGW64):**

```bash
python -m venv .venv
source .venv/Scripts/activate
which python  # .../nif-pt/.venv/Scripts/python.exe
```

> `venv/Scripts/activate` é Windows; `venv/bin/activate` só Linux. `Activate.ps1` só PS.

### 4.3 Instalar dependências

```bash
pip install -r requirements.txt
# requests>=2.31.0
# pyyaml>=6.0.1
# python-dotenv>=1.0.0
# pyodbc>=5.0.0
```

### 4.4 Verificar

```bash
python -c "from config.config import get_config; print(get_config('consulta_nif').keys())"
python -c "import consulta_nif; help(consulta_nif.validar_nif)"
python -c "from utils.error_handler import tratar_erro; help(tratar_erro)"
python consulta_nif.py 509442013  # requer NIF-PT-KEY
```

---

## 5. Configuração

### 5.1 `config/config.yaml` (37L)

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
consulta_nif:
  api_base: "http://www.nif.pt"
importar_nif_sqlite:
  db_path: "data/nif_pt.db"
  tabela: "nif_pt"
importar_nif:
  sql_server: "kiwa-pt-operations.database.windows.net"
  sql_database: "kiwa-pt-operations"
  sql_schema: "stg_nunotome"
  sql_driver: "ODBC Driver 18 for SQL Server"
  tabela_staging: "nif_pt_stg"
```

| Chave | Onde usada | Descrição |
|-------|------------|-----------|
| `timeout` | `consulta_nif.py:28` `requests.get(timeout=10)` | segundos (10s, não 1000) |
| `tempo_de_espera` | `consulta_nif.py:129` | retry rede/Timeout genérico 60s |
| `tempo_espera_minuto/hora` | `utils/error_handler.py:215` `get_tempo_espera()` | 60s / 3600s por janela rate-limit |
| `max_tentativas_global` | `consulta_nif.py:35` `MAX_TENTATIVAS_GLOBAL` | limite total (5) |
| `max_tentativas_minuto/hora/dia/mes` | `utils/error_handler.py:226` | 3 / 2 / 0 / 0 (0=abort) |
| `api_base` | `consulta_nif.py:26` | `http://www.nif.pt` |
| `db_path` | `importar_nif_sqlite.py:29` | `data/nif_pt.db` |

### 5.2 `config/.env` (+ `.env.example`)

```env
# NIF-PT — http://www.nif.pt/contactos/api/
NIF-PT-KEY=coloque_aqui

# Azure SQL — portal.azure.com → Connection strings
AZURE_USER=seu_user
AZURE_PALAVRA_CHAVE=sua_password

# Opcional futuro
# API_TOKEN=...
```

* `Copy-Item config\.env.example config\.env` e editar — **nunca** commitar (`.gitignore`).
* Nome **exato** `NIF-PT-KEY` com hífen — `NIF_PT_KEY` não é lido (`config.py:55`).

### 5.3 Precedência

`default` < bloco do script < `.env` — `config.py:45` `config.update(script_config)` (shallow merge).

---

## 6. Utilização — Modos de Operação

### 6.1 Modo 1 — Só consulta (sem gravar)

```powershell
python consulta_nif.py 509442013
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000  # replay determinístico
```

* Valida `isdigit` + `validar_nif()` Mod-11 (`consulta_nif.py:99`) — log `WARN` se falha mas **não bloqueia** request.
* `run_id` gerado em `consulta_nif.py:481` `ensure_run_id(cli_value=extract_cli_run_id())` (`utils/run_id.py:132`); `run_id` incluído em **todos** os JSON (`consultar_nif(nif, run_id)` `consulta_nif.py:171` + `utils/run_id.py:87` precedência `CLI>payload>ctx>gen`), log `[run] run_id=...` e `BOX | run_id |`.
* Se `NIF-PT-KEY` falta → `{"erro":"NIF-PT-KEY não encontrada","run_id":"..."} ` + `exit 1` (`consulta_nif.py:248`).
* Senão `GET http://www.nif.pt/?json=1&q=<NIF>&key=<KEY>` com `timeout 10s` e loop `max_global+1` com `tratar_erro(...,run_id)` + `guardar_erro(...,run_id)`.

### 6.2 Modo 2 — SQLite local

```powershell
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000 | python importar_nif_sqlite.py --run-id 550e8400-e29b-41d4-a716-446655440000
# stderr: <<nif-pt>> INFO - [sqlite] INSERT nif_pt nif=509442013 run_id=550e8400 -> 1 row em 0.02s
#         | Guardado em SQLite |
#         | run_id : 550e8400-e29b-41d4-a716-446655440000 |
```

* `get_db()` cria `data/nif_pt.db` + `nif_pt` (`CREATE TABLE IF NOT EXISTS` 5c `run_id TEXT`, `PRAGMA WAL`) + `idx_nif_pt_run_id` e `nif_api_erros` 15c via `init_error_table()`; migração idempotente `ALTER TABLE ADD COLUMN run_id TEXT`.
* `INSERT (nif, dados=JSON completo, data_consulta=datetime.now(), run_id)` (`importar_nif_sqlite.py:221`) herdado do JSON via `ensure_run_id(CLI>payload>ctx>gen)` (`:185`) com fallback se coluna falta.

### 6.3 Modo 3 — Azure SQL

```powershell
python consulta_nif.py 509442013 | python importar_nif.py
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000 | python importar_nif.py
# stderr: [db] INSERT stg_nunotome.nif_pt_stg nif=509442013 run_id=550e8400 -> 1 row
#         | Inserido em Azure SQL |
#         | run_id : 550e8400-e29b-41d4-a716-446655440000 |
```

* Pré: ODBC 18, `AZURE_USER/PALAVRA_CHAVE`, tabelas criadas via `sql/01_criar_tabelas.sql` (38c+41c `run_id`) + `sql/02_criar_tabela_erros.sql` (15c) + `sql/03_migracao_run_id.sql` se BD existente.
* `mapear_registo(resultado, run_id)` 37 cols (36+`run_id` `importar_nif.py:223`) → `INSERT` parametrizado `?` ×37 com `commit/rollback` + fallback 36c se coluna falta (`:529`).

### 6.4 Modo 4 — Ambos em simultâneo

**PowerShell (correção — `tee >( )` não existe):**

```powershell
$json = python consulta_nif.py 509442013          # inclui run_id
$json | python importar_nif_sqlite.py             # herda run_id do JSON
$json | python importar_nif.py                    # mesmo run_id — agrupável por run_id
# ou determinístico:
$rid = "550e8400-e29b-41d4-a716-446655440000"
$json = python consulta_nif.py 509442013 --run-id $rid
$json | python importar_nif_sqlite.py             # mesmo $rid
$json | python importar_nif.py                    # mesmo $rid mesmo sem --run-id
# ou:
python consulta_nif.py 509442013 | Tee-Object -FilePath temp.json | python importar_nif.py
python importar_nif_sqlite.py < temp.json         # herda run_id do JSON
```

**Bash (WSL/Git Bash):**

```bash
python consulta_nif.py 509442013 | tee >(python importar_nif_sqlite.py) | python importar_nif.py
```

### 6.5 Modo 5 — Ficheiro intermédio

```powershell
python consulta_nif.py 509442013 > resultado.json
python importar_nif_sqlite.py < resultado.json
python importar_nif.py < resultado.json
```

### 6.6 Batch (múltiplos NIFs)

**PowerShell:**

```powershell
Get-Content nifs.txt | ForEach-Object {
    python consulta_nif.py $_ | python importar_nif_sqlite.py
    Start-Sleep -Seconds 1  # respeitar rate-limit minuto
}
```

**Bash:**

```bash
while read nif; do
    python consulta_nif.py "$nif" | python importar_nif_sqlite.py
    sleep 1
done < nifs.txt
```

### 6.7 Help Python (v1.0.0)

```powershell
python -c "import consulta_nif; help(consulta_nif.validar_nif)"
python -c "import consulta_nif; help(consulta_nif.consultar_nif)"
python -c "from utils.error_handler import classificar_erro, tratar_erro; help(tratar_erro)"
python -c "from config.config import get_config; help(get_config)"
python -c "import importar_nif; help(importar_nif.mapear_registo)"
python -m pydoc consulta_nif
python -m pydoc utils.error_handler
```

Ver `docs/api/help.md` — transcrições verificadas.

---

## 7. Esquemas de Base de Dados

### 7.1 Visão comparativa

| Aspeto | SQLite `nif_pt` | SQLite `nif_api_erros` | Azure `nif_pt` | Azure `nif_pt_stg` | Azure `nif_api_erros` |
|--------|-----------------|------------------------|----------------|--------------------|-----------------------|
| Ficheiro | `data/nif_pt.db` | `data/nif_pt.db` | `kiwa-pt-operations` | idem | idem |
| Cols | 5 (4+`run_id`) | 15 (14+`run_id`) | 38 (37+`run_id`) | 41 (40+`run_id`) | 15 (14+`run_id`) |
| PK | `id AUTOINCREMENT` | `id AUTOINCREMENT` | `nif` | `id IDENTITY` | `id IDENTITY` |
| Histórico | Sim | Sim | Não (ouro) | Sim (`processado`) | Sim (`resolvido`) |
| DDL | `importar_nif_sqlite.py:55` + `03` | `utils/error_handler.py:46` + `03` | `sql/01_criar_tabelas.sql:21` | `sql/01_criar_tabelas.sql:99` | `sql/02_criar_tabela_erros.sql:20` |
| Estratégia | JSON bruto + `run_id` | Auditoria + `run_id` | 37c norm.+`run_id` | Staging + merge + `run_id` | Auditoria + `run_id` |
| Índice `run_id` | `idx_nif_pt_run_id` | `idx_nif_api_erros_run_id` | `ix_nif_pt_run_id` | `ix_nif_pt_stg_run_id` | `ix_nif_api_erros_run_id` |

### 7.2 SQLite — `nif_pt` (5c: 4+`run_id`)

```sql
CREATE TABLE IF NOT EXISTS nif_pt (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nif           INTEGER NOT NULL,
    dados         TEXT NOT NULL,          -- json.dumps(resultado, ensure_ascii=False) inclui run_id
    data_consulta TEXT NOT NULL DEFAULT (datetime('now')),
    run_id        TEXT                    -- UUID v4 da execução (utils/run_id.py:41)
);
CREATE INDEX IF NOT EXISTS idx_nif_pt_run_id ON nif_pt(run_id);
-- Migração idempotente (importar_nif_sqlite.py:102): PRAGMA table_info -> ALTER TABLE ADD COLUMN run_id TEXT
```

### 7.3 SQLite/Azure — `nif_api_erros` (15c: 14+`run_id`)

```sql
-- SQLite (utils/error_handler.py:46)
CREATE TABLE IF NOT EXISTS nif_api_erros (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nif           INTEGER,
    data_erro     TEXT NOT NULL DEFAULT (datetime('now')),
    tipo_erro     TEXT NOT NULL,          -- rate_limit_minute/hour/day/month/paid/unknown
    codigo_erro   TEXT,                   -- result da API
    mensagem      TEXT,                   -- message da API
    left_month    INTEGER, left_day INTEGER, left_hour INTEGER,
    left_minute   INTEGER, left_paid INTEGER,
    dados_json    TEXT NOT NULL,          -- JSON completo
    acao          TEXT,                   -- retry_60s / abort_day / none
    run_id        TEXT,                   -- UUID v4 da execução (utils/run_id.py:41)
    resolvido     INTEGER NOT NULL DEFAULT 0
);
-- Índices: idx_nif_api_erros_nif, idx_nif_api_erros_tipo, idx_nif_api_erros_run_id
-- Migração idempotente (utils/error_handler.py:153): PRAGMA table_info -> ALTER TABLE ADD COLUMN run_id TEXT
```

```sql
-- Azure SQL (sql/02_criar_tabela_erros.sql:20)
CREATE TABLE stg_nunotome.nif_api_erros (
    id            BIGINT IDENTITY(1,1) NOT NULL,
    nif           BIGINT NULL,
    data_erro     DATETIME2 NOT NULL DEFAULT GETDATE(),
    tipo_erro     NVARCHAR(50) NOT NULL,
    codigo_erro   NVARCHAR(50) NULL,
    mensagem      NVARCHAR(500) NULL,
    left_month    INT NULL, left_day INT NULL, left_hour INT NULL,
    left_minute   INT NULL, left_paid INT NULL,
    dados_json    NVARCHAR(MAX) NOT NULL,
    acao          NVARCHAR(50) NULL,
    run_id        NVARCHAR(36) NULL,       -- UUID v4 da execução
    resolvido     BIT NOT NULL DEFAULT 0,
    CONSTRAINT pk_nif_api_erros PRIMARY KEY CLUSTERED (id)
);
-- Índices: ix_nif_api_erros_nif, _tipo, _data, _run_id (sql/02:46 + sql/03:34)
```

### 7.4 Azure SQL — `nif_pt` (38c: 37+`run_id`, PK `nif`) e `nif_pt_stg` (41c: 40+`run_id`, PK `id`)

38 cols = `nif`, `nif_valido_formato`, `data_consulta`, `consulta_origem`, `seo_url`, `title`, `alias`, `status`, `start_date`, `activity`, `place_address/pc4/pc3/city`, `address/pc4/pc3/city`, `geo_region/county/parish`, `contacts_email/phone/website/fax`, `structure_nature/capital/capital_currency`, `cae`, `racius`, `portugalio`, `creditos_used`, `creditos_left_month/day/hour/minute/paid`, `run_id`.

`nif_pt_stg` = 38 + `id`, `data_staging`, `processado` (41). `colunas_tabela()` (`importar_nif.py:334`) lista 37 (inclui `run_id`, sem `id/data_*` com `DEFAULT`). Ver §7.5 migração.

Ver `docs/database/schema.md` para catálogo completo + ER Mermaid.

### 7.5 Criação e migração das tabelas

```powershell
# SSMS / Azure Data Studio / sqlcmd — novas BDs (01+02 já incluem run_id)
sqlcmd -S kiwa-pt-operations.database.windows.net -d kiwa-pt-operations -i sql/01_criar_tabelas.sql
sqlcmd -S kiwa-pt-operations.database.windows.net -d kiwa-pt-operations -i sql/02_criar_tabela_erros.sql

# BDs existentes — migração idempotente run_id (não faz DROP, seguro em prod)
sqlcmd -S kiwa-pt-operations.database.windows.net -d kiwa-pt-operations -i sql/03_migracao_run_id.sql
# Verificação:
# SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME='run_id';

# SQLite cria/migra nif_api_erros automaticamente no próximo consulta_nif.py (init_error_table + PRAGMA table_info)
# + importar_nif_sqlite.py:get_db() migra nif_pt run_id automaticamente
```

> `01_criar_tabelas.sql` faz `IF OBJECT_ID(...) IS NOT NULL DROP TABLE` — destrutivo. Em prod usar `IF NOT EXISTS CREATE`. Recomenda `CREATE INDEX ON nif_pt_stg(nif, processado) WHERE processado=0`.

---

## 8. Referência CLI

| Comando | Argumentos | stdin | stdout | stderr | Exit |
|---------|------------|-------|--------|--------|------|
| `consulta_nif.py` | `<NIF>` 9 dígitos `[--run-id UUID]` | — | JSON + `run_id` | `<<nif-pt>>` BOX/TAG/TIMING `[run]` | `0` ok, `1` erro |
| `importar_nif_sqlite.py` | `[--run-id UUID]` | JSON + `run_id` | — | `BOX Guardado em SQLite run_id` | `0/1` |
| `importar_nif.py` | `[--run-id UUID]` | JSON + `run_id` | — | `BOX Inserido em Azure SQL run_id` | `0/1` |

### 8.1 `consulta_nif.py`

```
Uso: python consulta_nif.py <NIF> [--run-id <uuid>]
Exemplo: python consulta_nif.py 509442013
         python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000
         python consulta_nif.py 509442013 --run-id=550e8400-e29b-41d4-a716-446655440000
```

* `TIMEOUT 10s` + `max_tentativas_global 5` + `retry 60s/3600s` via `error_handler` com `run_id`.
* `run_id` UUID v4 gerado por `utils/run_id.py:41` `generate_run_id()` + `ensure_run_id(CLI>payload>ctx>gen)` (`consulta_nif.py:481`); `remove_run_id_args` mantém `isdigit` posicional; `--run-id` suportado como `UUID` e `=UUID` (`utils/run_id.py:132`).
* `help(consulta_nif.validar_nif)` / `help(consulta_nif.consultar_nif)` / `help(utils.run_id.generate_run_id)` para docstrings PEP 257.

### 8.2 Importadores

```
Uso: python consulta_nif.py 509442013 | python importar_nif_sqlite.py [--run-id UUID]
     python importar_nif_sqlite.py < ficheiro.json
     python importar_nif_sqlite.py --run-id 550e8400-e29b-41d4-a716-446655440000 < ficheiro.json
     python consulta_nif.py 509442013 | python importar_nif.py [--run-id UUID]
```

* Precedência `run_id`: `CLI --run-id` > `JSON payload run_id` > `ContextVar` > `uuid4` (`importar_nif.py:455` / `importar_nif_sqlite.py:185` `ensure_run_id`); herança automática via JSON é o recomendado (pipe sem `--run-id` no importador).

---

## 9. Referência de Dados e JSON

### 9.1 Exemplo JSON sucesso (509442013, 2026-09-10) — com `run_id`

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": "nif.pt",
  "erro": null,
  "dados": {
    "nif": 509442013,
    "seo_url": "nexperience-lda",
    "title": "Nexperience, Unipessoal, Lda",
    "alias": "Nexperience",
    "status": "active",
    "start_date": "2010-05-18",
    "activity": "<p>Desenvolvimento de software...</p>",
    "address": "Rua de Santa Catarina, Nº 1232",
    "pc4": "4000", "pc3": "457", "city": "Porto",
    "place": { "address": "Rua ...", "pc4": "4000", "pc3": "457", "city": "Porto" },
    "geo": { "region": "Porto", "county": "Porto", "parish": "Cedofeita" },
    "contacts": { "email": "info@nex.pt", "phone": "220 198 228", "website": "www.nex.pt", "fax": "224 905 459" },
    "structure": { "nature": "UNI", "capital": "248000.00", "capital_currency": "EUR" },
    "cae": ["62010", "63120", "62020", "46510"],
    "racius": "https://www.racius.com/nexperience-lda/",
    "portugalio": null
  },
  "nif_valido_formato": true,
  "creditos": { "used": "free", "left": [] },
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```
`run_id` gerado por `utils/run_id.py:41` (`generate_run_id()` UUID v4) em `consulta_nif.py:481` `ensure_run_id()` e propagado via `stdout` → `stdin` importadores (`importar_nif.py:455` / `importar_nif_sqlite.py:185`); todos os JSON (sucesso e erro) incluem `run_id`.

### 9.2 Exemplo JSON erro rate-limit (classificado v1.0.0 + `run_id`)

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": "nif.pt",
  "erro": "Limit per minute exceeded",
  "dados": {
    "result": "error",
    "message": "Limit per minute exceeded",
    "credits": { "left": { "minute": 0, "hour": 9, "day": 99, "month": 999 } }
  },
  "tipo_erro": "rate_limit_minute",
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Persistido em `nif_api_erros` 15c com `run_id` e `acao=retry_60s` (`utils/error_handler.py:368` `guardar_erro(...,run_id)`) e retry automático 60s (max 3); `SELECT * FROM nif_api_erros WHERE run_id='550e8400-...'` agrupa retries da mesma execução.

### 9.3 Exemplo JSON `No records` (com `run_id`)

```json
{
  "nif": "999999999",
  "valido": false,
  "fonte": "nif.pt",
  "erro": "No records found",
  "dados": { "result": "No records found", "nif_validation": false },
  "tipo_erro": "generic_error",
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 9.4 Mapeamento `mapear_registo(resultado, run_id)` → SQL

`importar_nif.py:223` desembrulha `dados.{place,geo,contacts,structure}` + `creditos` + `run_id` (`utils/run_id.py:87`):

| API | SQL | Parser |
|-----|-----|--------|
| `dados.seo_url` | `seo_url` | direto |
| `dados.cae` lista | `cae` | `extrair_cae() -> ",".join` |
| `dados.start_date` | `start_date` | `parse_date() -> date` |
| `structure.capital` | `structure_capital` | `parse_capital() ","→"."` |
| `creditos.left.month` | `creditos_left_month` | `parse_int()` |
| `resultado.run_id` / `run_id` param | `run_id` | `ensure_run_id()` `CLI>payload>ctx` |

`colunas_tabela()` 37 nomes (36+`run_id` `importar_nif.py:334`) — `parse_*` devolve `None` → `NULL`; `run_id` `NVARCHAR(36)` indexado.

### 9.5 Caso `creditos.left`

* **Pago:** `{"month":999,"day":99,"hour":9,"minute":0,"paid":0}` → `parse_int`.
* **Free (real 2026-09-10):** `[]` → `importar_nif.py:116` `or {}` → `NULL` em SQL (não crasha).

### 9.6 Validação Mod-11

```python
total = sum(int(d) * (9 - i) for i, d in enumerate(nif[:8]))
resto = total % 11
digito = 0 if resto in (0, 1) else 11 - resto
return digito == int(nif[8])
```

`help(consulta_nif.validar_nif)` para docstring completa + exemplos.

### 9.7 Campo `run_id` (v1.1.0)

* **Tipo:** `str` UUID v4 `xxxxxxxx-xxxx-4xxx-xxxx-xxxxxxxxxxxx` (36c, 4 hífens) gerado por `utils/run_id.py:41` `generate_run_id()`.
* **Presença:** sempre em `stdout` JSON (sucesso e erro, incluindo `NIF-PT-KEY` falta, timeout, `result != success`) — ver `consulta_nif.py:237` `run_id` em todos os `return`.
* **Propagação:** `stdout` JSON `run_id` → `stdin` importadores via `ensure_run_id(CLI>payload>ctx>gen)` (`importar_nif_sqlite.py:185` / `importar_nif.py:455`); precedência `CLI --run-id` > `payload` > `ContextVar` > `uuid4`.
* **Persistência:** `nif_pt.run_id` / `nif_pt_stg.run_id` / `nif_api_erros.run_id` (`NVARCHAR36`/`TEXT`) + índices `run_id`; SQLite migração automática, Azure `sql/03_migracao_run_id.sql`.
* **Exemplo:** `python -c "from utils.run_id import generate_run_id; print(generate_run_id())"` → `550e8400-e29b-41d4-a716-446655440000`.

---

## 10. Códigos de Erro e Saída

| `erro` | `tipo_erro` | `exit` | Significado | Ação `error_handler` | Retry |
|--------|-------------|--------|-------------|----------------------|-------|
| `null` | — | `0` | Sucesso | — | — |
| `Uso: ... <NIF>` | — | `1` | Sem argv | — | — |
| `NIF deve conter apenas dígitos` | — | `1` | `isdigit` fail | — | — |
| `NIF-PT-KEY não encontrada` | — | `1` | sem chave | — | — |
| `Timeout na consulta` | — | `1` | `requests.Timeout` | — | `sleep 60s` se `<max_global` |
| `Erro de rede: ...` | — | `1` | `RequestException` | — | idem |
| `Resposta inválida (não JSON)` | — | `1` | `JSONDecodeError` | — | — |
| `Limit per minute` | `rate_limit_minute` | `1` | quota minuto | `retry_60s` | 60s, max 3 + global 5 |
| `Limit per hour` | `rate_limit_hour` | `1` | quota hora | `retry_3600s` | 3600s, max 2 |
| `Limit per day` | `rate_limit_day` | `1` | quota dia | `abort_day` BOX fatal | 0 (abort) |
| `Limit per month` | `rate_limit_month` | `1` | quota mês | `abort_month` BOX fatal | 0 |
| `Limit per ... paid` | `rate_limit_paid` | `1` | sem créditos pagos | `abort_paid` | 0 |
| `No records found` / `error` | `generic_error` | `1` | sem registo público | `none` auditoria | 0 |
| `Nenhum JSON no stdin` | — | `1` | pipe vazio | — | — |

Importadores propagam `resultado.erro` — se `consulta_nif` falhou, não inserem. `tipo_erro` só em erros classificados. Todos os JSON (sucesso e erro) incluem `run_id` para `SELECT ... WHERE run_id=?`.

---

## 11. Logging

### 11.1 Configuração v1.1.0 (run_id)

`Logging/logging_orchestrator.py` (580L) — **integrado** em todos os scripts (`setup_logging()`) com TAG `[run]`:

* `LOG_LEVEL_GLOBAL/FILE/CONSOLE = INFO` · `FILE_ULTRA_DEBUG/CONSOLE_ULTRA_DEBUG = True`.
* `LOG_FOLDER='log_files'`, `LOG_OUTPUT_FILE='log_files/nif_pt.log'`, prefixo `<<nif-pt>>`.
* `LOG_FORMAT_FILE='<<nif-pt>> %(asctime)s - %(name)s - %(levelname)s - %(message)s'` + ultra-debug `%(filename)s - %(funcName)s - %(lineno)d` em `DEBUG`.
* `RotatingFileHandler` 10 MB / 5000 recs / 10 backups (`logging_orchestrator.py:64`).

### 11.2 Livro de estilo R1–R9

| # | Estilo | Char | Width | Nível | Uso |
|---|--------|------|-------|-------|-----|
| 1 | `BANNER_APP_START/END` | `=` | 49 | INFO | `nif-pt consulta_nif a iniciar/finalizado` |
| 3 | `BANNER_SECTION` | `-` | 49 | INFO | `Inserir staging` |
| 5 | `BANNER_FUNCTION` | `~` | 49 | DEBUG | `validar_nif()` `consultar_nif()` `mapear_registo()` |
| 6 | `TAG` | `[tag]` | — | herda | `[api][valid][cfg][db][sqlite][io][map][erro][rate-limit][cli][run]` |
| 7 | `SEPARATOR` | `-` | 49 | DEBUG | `---------------------------------------------------` |
| 8 | `BOX` | `-\|` | 49 | INFO | `| NIF : 509442013 |` `| Consulta com sucesso |` `| run_id : 550e8400-... |` |
| 9 | `TIMING` | `%.2fs` | — | INFO/DEBUG | `Aplicação concluída em 0.92s` `validar_nif -> 0.00s` |

Regras: `R1 WIDTH=49 ≤79`, `R4 [tag] lowercase`, `R6 f"{' title ':=^49}"`, `R9 %.2fs` via `time.perf_counter()`.

### 11.3 Exemplo de saída

```
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ========= nif-pt consulta_nif a iniciar =========
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [run] run_id=550e8400-e29b-41d4-a716-446655440000
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - INFO - [api] GET http://www.nif.pt?q=509442013 key=***XXXX timeout=10s
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - WARNING - [rate-limit] Limite por minuto nif=509442013 left_minute=0 — espera 60s retry tipo 1/3 global 1/5
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - INFO - [api] NIF 509442013 válido=True credits used=free left=[] (0.85s) run_id=550e8400
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | Consulta com sucesso                          |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | NIF         : 509442013                    |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | run_id      : 550e8400-e29b-41d4-a716-...  |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [run] run_id=550e8400-e29b-41d4-a716-446655440000
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - Aplicação concluída em 0.92s
```

Ver `docs/guides/logging.md` + `docs/technical.md` §11 (logging) + §10b (run_id).

---

## 12. Exemplos Práticos (PowerShell & Bash)

### 12.1 Consultar + SQLite

| PowerShell | Bash |
|------------|------|
| `python consulta_nif.py 509442013 \| python importar_nif_sqlite.py` | idem |

### 12.2 Consultar + Azure

| PowerShell | Bash |
|------------|------|
| `python consulta_nif.py 509442013 \| python importar_nif.py` | idem |

### 12.3 Ambos

| PowerShell | Bash |
|------------|------|
| `$j = python consulta_nif.py 509442013`<br>`$j \| python importar_nif_sqlite.py`<br>`$j \| python importar_nif.py` | `python consulta_nif.py 509442013 \| tee >(python importar_nif_sqlite.py) \| python importar_nif.py` |

### 12.4 Batch

**PowerShell:**

```powershell
Get-Content nifs.txt | ForEach-Object {
    Write-Host "A consultar $_"
    python consulta_nif.py $_ | python importar_nif_sqlite.py
    Start-Sleep -Seconds 1
}
```

**Bash:**

```bash
while read nif; do echo "A consultar $nif"; python consulta_nif.py "$nif" | python importar_nif_sqlite.py; sleep 1; done < nifs.txt
```

### 12.5 Histórico SQLite (com `run_id`)

```powershell
python -c "import sqlite3,json; conn=sqlite3.connect('data/nif_pt.db'); [print(f'{r[0]}: {r[1]} - {json.loads(r[2])[\"dados\"][\"title\"]} run_id={r[3][:8]}') for r in conn.execute('SELECT id,nif,dados,run_id FROM nif_pt ORDER BY data_consulta DESC LIMIT 5')]"
sqlite3 data/nif_pt.db "SELECT id,nif,substr(run_id,1,8),data_consulta FROM nif_pt ORDER BY data_consulta DESC LIMIT 5;"
sqlite3 data/nif_pt.db "SELECT tipo_erro,COUNT(*) FROM nif_api_erros GROUP BY tipo_erro;"
sqlite3 data/nif_pt.db "SELECT run_id, COUNT(*) FROM nif_pt GROUP BY run_id ORDER BY data_consulta DESC LIMIT 5;"
sqlite3 data/nif_pt.db "SELECT run_id, tipo_erro, COUNT(*) FROM nif_api_erros GROUP BY run_id, tipo_erro;"
```

### 12.6 Validar sem créditos + `run_id`

```powershell
python -c "from consulta_nif import validar_nif; print(validar_nif('509442013'))"  # True
python -c "from consulta_nif import validar_nif; print(validar_nif('123456789'))"  # False
python -c "from utils.error_handler import classificar_erro; print(classificar_erro({'result':'error','message':'Limit per minute'}))"
python -c "from utils.run_id import generate_run_id, ensure_run_id; print(generate_run_id()); print(ensure_run_id(payload_value='550e8400-e29b-41d4-a716-446655440000'))"
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000 | ConvertFrom-Json | Select-Object nif, run_id, tipo_erro
```

---

## 13. Resolução de Problemas (Troubleshooting)

### 13.1 `NIF-PT-KEY não encontrada`

1. `Test-Path config\.env` + `Get-Content config\.env` → deve ter `NIF-PT-KEY=xxxxx` com hífen, sem espaços.
2. `os.getenv("NIF-PT-KEY")` em `config.py:55` — `NIF_PT_KEY` não funciona.
3. Solicitar chave em http://www.nif.pt/contactos/api/.

### 13.2 `Limit per minute/hour` — rate-limit com retry

* `utils/error_handler.py:426` aguarda `60s` (minuto, max 3) ou `3600s` (hora, max 2) com limite global 5. Log: `[rate-limit] Limite por minuto nif=... espera 60s retry tipo 1/3 global 1/5`.
* Ver `SELECT * FROM nif_api_erros WHERE tipo_erro='rate_limit_minute' ORDER BY data_erro DESC` + `log_files/nif_pt.log`.
* Se exceder `max_tentativas_*` → `abort_retry_esgotado` com `motivo=max_tipo/max_global`.

### 13.3 `Limit per day/month` — quota fatal

* `max_tentativas_dia/mes = 0` → `abort` imediato + BOX `Erro fatal - quota diária/mensal excedida` + `exit 1`.
* Persistido com `acao=abort_day/month` — consultar `nif_api_erros` para auditoria.

### 13.4 `No records found`

NIF válido sem registo público — não é erro de código; `importar_*.py` não insere; `tipo_erro=generic_error`.

### 13.5 `database is locked` (SQLite)

`importar_nif_sqlite.py:50` `PRAGMA journal_mode=WAL` já mitiga; se persistir: `PRAGMA busy_timeout=5000` ou serializar writes.

### 13.6 Validação Mod-11 não bloqueia request

`validar_nif()` só afeta `valido`; `main()` só valida `isdigit`. `123456789` (dígito errado) faz request e gasta crédito. Filtrar antes:

```powershell
python -c "from consulta_nif import validar_nif; import sys; sys.exit(0 if validar_nif('123456789') else 1)" -and python consulta_nif.py 123456789
```

### 13.7 Azure SQL `pyodbc.Error`

1. `Test-Path config\.env` + `AZURE_USER/PALAVRA_CHAVE`.
2. `Get-OdbcDriver -Name "*Driver 18*"` — instalar ODBC 18 se falta.
3. Whitelist IP no Portal Azure → SQL → Networking.
4. `Encrypt=yes;TrustServerCertificate=no` (`importar_nif.py:47`) — se SSL erro, verificar cert.

### 13.8 `tee` não funciona em PowerShell

`tee >( )` é Bash; em PS usar variável `$json` ou `Tee-Object`.

### 13.9 `ModuleNotFoundError: yaml`

`pip uninstall yaml -y; pip install pyyaml python-dotenv pyodbc` ou `pip install -r requirements.txt` (fix v1.0.0).

---

## 14. FAQ

**1. Custo?** Free limitado (`credits.left: []`); paid com `left: {month/day/hour/minute/paid}`.

**2. Créditos?** `creditos.left` dict se `paid`, `[]` se `free`; `importar_nif` → `NULL` se `[]`.

**3. SQLite vs Azure?** SQLite JSON bruto (5c 4+`run_id` WAL) flexível; Azure 37 cols + `run_id` + `nif_api_erros` 15c analítico.

**4. Mod-11?** `Σ d*(9-i)%11 → 0 se resto 0/1 senão 11-resto` == `d[8]` (`consulta_nif.py:99`, `help(validar_nif)`).

**5. Batch?** Sim, `sleep 1` + retry automático `60s/3600s` já trata `rate_limit`; cada iteração tem `run_id` único — agrupar por `run_id`.

**6. `nif_api_erros`?** Auditoria de todos os erros; `SELECT tipo_erro, mensagem, left_minute, acao, run_id FROM nif_api_erros` + `WHERE run_id='...'` por execução.

**7. `main.py`?** `92L` `ensure_run_id()` por execução + stub `BANNER+BOX`; futuro `cli.py --nif --to {sqlite,azure,both}`.

**8. `stg_nunotome`?** Schema pessoal (`config.yaml:33`); mudar para `stg/dbo` se partilhar.

**9. Help Python?** `help(consulta_nif.validar_nif)`, `help(utils.error_handler.tratar_erro)`, `help(utils.run_id.generate_run_id)` (ver `docs/api/help.md`).

**10. Histórico?** `SELECT * FROM nif_pt ORDER BY data_consulta DESC` (SQLite) ou `stg_nunotome.nif_pt_stg WHERE processado=0` (Azure); filtrar por `WHERE run_id='...'` para uma execução.

**11. `run_id`?** UUID v4 por execução (`utils/run_id.py:41`); `python consulta_nif.py 509442013 --run-id <uuid>` determinístico; propagação `CLI>payload>ctx>gen` via JSON `run_id`; ver `docs/technical.md` §10b.

---

## 15. Anexos

### 15.1 Glossário

Ver [docs/glossary.md](docs/glossary.md). Termos: NIF, Mod-11, CAE, WAL, ODBC, `stg`, `creditos.left`, `nif_valido_formato`, `get_config`, `RotatingFileHandler`, `BOX/TAG/TIMING`, `rate_limit_*`, ADR, C4, `run_id`, `ContextVar`, `ensure_run_id`.

### 15.2 Estrutura de ficheiros (v1.1.0 run_id)

```
nif-pt/
├── consulta_nif.py               # 570L — validar + GET + retry per-tipo+global + run_id + --run-id
├── importar_nif.py               # 576L — 37 cols (36+run_id) → Azure staging + --run-id
├── importar_nif_sqlite.py        # 268L — JSON → SQLite WAL 5c + run_id + --run-id + migração
├── utils/run_id.py               # 191L — generate_run_id UUID v4 + ContextVar + ensure_run_id + --run-id parse
├── utils/error_handler.py        # 806L — classificar + tratar(...,run_id) + guardar(...,run_id) + init 15c run_id
├── main.py                       # 92L — ensure_run_id por execução + stub
├── Logging/logging_orchestrator.py # 580L — R1-R9, <<nif-pt>>, 10MB/5000/10, TAG [run]
├── config/config.py              # 70L — get_config() + ***
├── config/config.yaml            # 37L — default 11 chaves + 3 blocos
├── sql/01_criar_tabelas.sql      # 169L — nif_pt 38c (37+run_id) + nif_pt_stg 41c (40+run_id) + idx run_id
├── sql/02_criar_tabela_erros.sql # 47L — nif_api_erros 15c (14+run_id) + idx run_id
├── sql/03_migracao_run_id.sql    # 39L — migração idempotente run_id (ALTER + INDEX) para BDs existentes
├── docs/technical.md             # v1.1.0 — C4 + sequência run_id + ER 38/41/15c + catálogo + ADRs (ADR-009)
├── docs/api/help.md              # help() verificado (validar_nif, consultar_nif, generate_run_id)
├── docs/architecture/            # C4 + diagramas Mermaid v1.1.0 + ADR-009 run_id
├── docs/database/schema.md       # ER 38/41/15c + run_id + 03_migracao_run_id.sql
├── docs/api/nif-pt-api.md        # contrato nif.pt
├── data/nif_pt.db                # WAL, ignorado (auto-migra run_id)
├── log_files/nif_pt.log          # RotatingFileHandler, ignorado (BOX run_id)
├── requirements.txt              # requests, pyyaml, dotenv, pyodbc
├── README.md                     # porta de entrada v1.1.0
├── CHANGELOG.md                  # v1.1.0
└── MANUAL.md                     # este ficheiro
```

### 15.3 Changelog resumido

Ver [CHANGELOG.md](CHANGELOG.md) — `v1.1.0` adiciona `run_id` (rastreabilidade por execução); `v1.0.0` promove `beta` com `error_handler` + `logging_orchestrator` + `max_tentativas_*`.

### 15.4 Referências

* `nif.pt` API: `GET http://www.nif.pt/?json=1&q=<NIF>&key=<KEY>` (`consulta_nif.py:272`)
* `config/config.py:30` `get_config()` · `utils/error_handler.py:515` `tratar_erro(...,run_id)` · `utils/run_id.py:41` `generate_run_id` / `:87` `ensure_run_id` · `Logging/logging_orchestrator.py:226` `setup_logging()` + TAG `[run]`
* `sql/03_migracao_run_id.sql` migração idempotente · `importar_nif.py:334` `colunas_tabela()` 37c
* [docs/technical.md](docs/technical.md) §10b run_id · [docs/architecture/diagrams.md](docs/architecture/diagrams.md) · [docs/api/help.md](docs/api/help.md) · [docs/database/schema.md](docs/database/schema.md) 38/41/15c
